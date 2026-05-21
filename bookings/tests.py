from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bookings.models import (
    BookingGroup,
    BookingItem,
    BookingLine,
    BookingPayment,
    BookingStatus,
)
from bookings.payment_validity import booking_has_valid_payment, is_valid_booking_payment
from companies.models import Company
from bookings.pdf_build import (
    _currency_for_account,
    _ensure_pdf_unicode_fonts,
    _format_money,
    _group_into_blocks,
    _unordered_package_item_rows,
    _package_item_lines_for_supplier_line,
)
from bookings.pricing import resolve_booking_line_price
from bookings.supplier_line import (
    _package_query_for_supplier_line,
    package_for_supplier_booking_line,
    prepare_supplier_field_dict,
)
from bookings.supplier_capacity import supplier_booking_capacity_status
from bookings.unique_id import allocate_booking_unique_id, format_booking_unique_id
from countries.models import Country
from packages.models import Package, PackageItem, PackageVersion
from suppliers.models import SupplierType, Tier
from users.models import Account
from users.supplier_price import resolve_active_package_for_supplier_tier


class BookingUniqueIdTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(
            name='Test Account',
            country=country,
        )
        self.company = Company.objects.create(
            account=self.account,
            name='Main',
            supplier_type=supplier_type,
            is_main=True,
        )

    def test_format_booking_unique_id(self):
        self.assertEqual(format_booking_unique_id(2026, 1), '26-0001')
        self.assertEqual(format_booking_unique_id(2026, 42), '26-0042')

    def test_allocate_increments_per_company_and_year(self):
        when = timezone.datetime(2026, 3, 15, tzinfo=timezone.utc)
        first = allocate_booking_unique_id(self.company.id, self.account.id, when=when)
        second = allocate_booking_unique_id(self.company.id, self.account.id, when=when)
        self.assertEqual(first, '26-0001')
        self.assertEqual(second, '26-0002')

    def test_allocate_resets_each_calendar_year(self):
        y2025 = timezone.datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc)
        y2026 = timezone.datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(allocate_booking_unique_id(self.account.id, when=y2025), '25-0001')
        self.assertEqual(allocate_booking_unique_id(self.account.id, when=y2026), '26-0001')

    def test_sequences_are_independent_per_account(self):
        other = Account.objects.create(name='Other', country=self.account.country)
        when = timezone.datetime(2026, 6, 1, tzinfo=timezone.utc)
        self.assertEqual(allocate_booking_unique_id(self.account.id, when=when), '26-0001')
        self.assertEqual(allocate_booking_unique_id(other.id, when=when), '26-0001')


class BookingLinePricingTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(
            name='Test Account',
            country=country,
        )
        self.company = Company.objects.create(
            account=self.account,
            name='Main',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.status = BookingStatus.objects.create(
            account=self.account,
            title='New',
        )
        self.booking = BookingItem.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0001',
            title='Wedding',
        )
        self.group = BookingGroup.objects.create(booking=self.booking, name='Services')

    def _line(self, **kwargs):
        defaults = {
            'account': self.account,
            'booking': self.booking,
            'booking_group': self.group,
            'label': 'Item',
            'field_type': 'text',
            'value': '',
        }
        defaults.update(kwargs)
        return BookingLine.objects.create(**defaults)

    def test_checkbox_price_only_when_checked(self):
        line = self._line(field_type='checkbox', price=Decimal('25.00'), value='false')
        self.assertIsNone(resolve_booking_line_price(line))
        line.value = 'true'
        line.save(update_fields=['value'])
        self.assertEqual(resolve_booking_line_price(line), Decimal('25.00'))

    def test_select_uses_option_price(self):
        line = self._line(
            field_type='select',
            value='Gold',
            options=[{'label': 'Gold', 'price': '99.50'}],
        )
        self.assertEqual(resolve_booking_line_price(line), Decimal('99.50'))


class BookingSupplierLineStorageTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(name='Tenant', country=country)
        self.supplier = Company.objects.create(
            account=self.account,
            name='Supplier Co',
            supplier_type=supplier_type,
        )
        self.tier = Tier.objects.create(
            account=self.account,
            company=self.supplier,
            name='Gold',
        )
        past = timezone.now() - timedelta(days=1)
        self.version = PackageVersion.objects.create(
            title='V1',
            effectivity_date=past,
            company=self.supplier,
            account=self.account,
        )
        self.package = Package.objects.create(
            package_version=self.version,
            tier=self.tier,
            company=self.supplier,
            account=self.account,
            total_price=Decimal('100.00'),
            is_active=True,
        )

    def test_prepare_supplier_field_dict_sets_fks_and_clears_value(self):
        fv = {
            'field_type': 'supplier',
            'label': 'Venue',
            'value': (
                f'{{"tier_id": {self.tier.id}, "supplier_id": {self.supplier.id}, '
                f'"price": "75.00"}}'
            ),
            'price': None,
        }
        prepare_supplier_field_dict(fv)
        self.assertEqual(fv['company_id'], self.supplier.id)
        self.assertEqual(fv['tier_id'], self.tier.id)
        self.assertEqual(fv['package_version_id'], self.version.id)
        self.assertEqual(fv['value'], '')
        self.assertEqual(fv['price'], '75.00')

    def test_package_query_when_package_version_id_is_package_pk(self):
        """Some rows may store ``packages.id`` in ``package_version_id``."""
        pkg = _package_query_for_supplier_line(
            self.supplier.id,
            self.tier.id,
            self.package.id,
        )
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.id, self.package.id)

    def test_package_for_supplier_booking_line_uses_stored_fks(self):
        status = BookingStatus.objects.create(account=self.account, title='New')
        main = Company.objects.create(
            account=self.account,
            name='Main',
            supplier_type=SupplierType.objects.create(name='MainType'),
            is_main=True,
        )
        booking = BookingItem.objects.create(
            account=self.account,
            company=main,
            status=status,
            unique_id='26-0201',
            title='Event',
        )
        group = BookingGroup.objects.create(booking=booking, name='Services')
        line = BookingLine.objects.create(
            account=self.account,
            booking=booking,
            booking_group=group,
            label='Venue',
            field_type='supplier',
            company=self.supplier,
            tier=self.tier,
            package_version=self.version,
            value='',
        )
        pkg = package_for_supplier_booking_line(line)
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.id, self.package.id)

    def test_resolve_price_from_supplier_fks_without_value(self):
        status = BookingStatus.objects.create(account=self.account, title='New')
        main = Company.objects.create(
            account=self.account,
            name='Main',
            supplier_type=SupplierType.objects.create(name='MainType'),
            is_main=True,
        )
        booking = BookingItem.objects.create(
            account=self.account,
            company=main,
            status=status,
            unique_id='26-0200',
            title='Event',
        )
        group = BookingGroup.objects.create(booking=booking, name='Services')
        line = BookingLine.objects.create(
            account=self.account,
            booking=booking,
            booking_group=group,
            label='Venue',
            field_type='supplier',
            company=self.supplier,
            tier=self.tier,
            package_version=self.version,
            price=Decimal('88.00'),
            value='',
        )
        self.assertEqual(resolve_booking_line_price(line), Decimal('88.00'))


class BookingPdfCurrencyTests(TestCase):
    def setUp(self):
        self.philippines = Country.objects.create(
            name='Philippines',
            iso_code='PHL',
            iso2_code='PH',
            currency='Philippine peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        self.account = Account.objects.create(
            name='PH Account',
            country=self.philippines,
        )

    def test_currency_for_philippines_account(self):
        symbol, code = _currency_for_account(self.account)
        self.assertEqual(symbol, '₱')
        self.assertEqual(code, 'PHP')

    def test_format_money_uses_peso_when_unicode_font_available(self):
        self.assertTrue(_ensure_pdf_unicode_fonts())
        self.assertEqual(
            _format_money(Decimal('100.00'), '₱', 'PHP'),
            '₱ 100.00',
        )

    def test_format_money_falls_back_to_code_without_unicode_font(self):
        with patch('bookings.pdf_build._ensure_pdf_unicode_fonts', return_value=False):
            self.assertEqual(
                _format_money(Decimal('100.00'), '₱', 'PHP'),
                'PHP 100.00',
            )


class BookingPdfPackageItemsTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(name='Tenant', country=country)
        self.supplier = Company.objects.create(
            account=self.account,
            name='Supplier Co',
            supplier_type=supplier_type,
        )
        self.tier = Tier.objects.create(
            account=self.account,
            company=self.supplier,
            name='Gold',
        )
        past = timezone.now() - timedelta(days=1)
        self.version = PackageVersion.objects.create(
            title='V1',
            effectivity_date=past,
            company=self.supplier,
            account=self.account,
        )
        self.package = Package.objects.create(
            package_version=self.version,
            tier=self.tier,
            company=self.supplier,
            account=self.account,
            total_price=Decimal('100.00'),
            is_active=True,
        )

    def test_unordered_package_item_rows_nested(self):
        root_a = PackageItem.objects.create(
            package=self.package,
            parent=None,
            title='Main service',
            company=self.supplier,
            account=self.account,
            sort_order=0,
        )
        PackageItem.objects.create(
            package=self.package,
            parent=root_a,
            title='Sub A',
            company=self.supplier,
            account=self.account,
            sort_order=0,
        )
        PackageItem.objects.create(
            package=self.package,
            parent=None,
            title='Second',
            company=self.supplier,
            account=self.account,
            sort_order=1,
        )
        rows = _unordered_package_item_rows(self.package)
        self.assertEqual(
            rows,
            [(0, 'Main service'), (1, 'Sub A'), (0, 'Second')],
        )

    def test_group_into_blocks_includes_package_items_for_supplier_line(self):
        status = BookingStatus.objects.create(account=self.account, title='New')
        main = Company.objects.create(
            account=self.account,
            name='Main',
            supplier_type=SupplierType.objects.create(name='X'),
            is_main=True,
        )
        booking = BookingItem.objects.create(
            account=self.account,
            company=main,
            status=status,
            unique_id='26-0098',
            title='Event',
        )
        group = BookingGroup.objects.create(booking=booking, name='Suppliers')
        PackageItem.objects.create(
            package=self.package,
            parent=None,
            title='Included item',
            company=self.supplier,
            account=self.account,
        )
        line = BookingLine.objects.create(
            account=self.account,
            booking=booking,
            booking_group=group,
            label='Venue',
            field_type='supplier',
            company=self.supplier,
            tier=self.tier,
            package_version=self.version,
            price=Decimal('50.00'),
            value='',
        )
        blocks = _group_into_blocks([line], {}, {self.tier.id: 'Gold'})
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].package_items, [(0, 'Included item')])

    def test_package_item_lines_for_supplier_booking_line(self):
        status = BookingStatus.objects.create(account=self.account, title='New')
        main = Company.objects.create(
            account=self.account,
            name='Main',
            supplier_type=SupplierType.objects.create(name='X'),
            is_main=True,
        )
        booking = BookingItem.objects.create(
            account=self.account,
            company=main,
            status=status,
            unique_id='26-0099',
            title='Event',
        )
        group = BookingGroup.objects.create(booking=booking, name='Services')
        PackageItem.objects.create(
            package=self.package,
            parent=None,
            title='Included item',
            company=self.supplier,
            account=self.account,
        )
        line = BookingLine.objects.create(
            account=self.account,
            booking=booking,
            booking_group=group,
            label='Venue',
            field_type='supplier',
            company=self.supplier,
            tier=self.tier,
            package_version=self.version,
            price=Decimal('50.00'),
            value='',
        )
        found = _package_item_lines_for_supplier_line(line)
        self.assertEqual(found, [(0, 'Included item')])

    def test_package_item_lines_empty_without_package(self):
        status = BookingStatus.objects.create(account=self.account, title='New')
        main = Company.objects.create(
            account=self.account,
            name='Main',
            supplier_type=SupplierType.objects.create(name='Y'),
            is_main=True,
        )
        booking = BookingItem.objects.create(
            account=self.account,
            company=main,
            status=status,
            unique_id='26-0100',
            title='Event',
        )
        group = BookingGroup.objects.create(booking=booking, name='Services')
        line = BookingLine.objects.create(
            account=self.account,
            booking=booking,
            booking_group=group,
            label='Venue',
            field_type='supplier',
            price=Decimal('10.00'),
            value=f'{{"tier_id": {self.tier.id}, "supplier_id": {self.supplier.id + 9999}}}',
        )
        self.assertEqual(_package_item_lines_for_supplier_line(line), [])

    def test_resolve_active_package_requires_active_version(self):
        self.version.is_active = False
        self.version.save(update_fields=['is_active'])
        self.assertIsNone(
            resolve_active_package_for_supplier_tier(self.supplier.id, self.tier.id),
        )

    def test_resolve_uses_latest_active_eligible_version(self):
        """When a newer version exists but is inactive, use the prior active row."""
        self.version.effectivity_date = timezone.now() - timedelta(days=30)
        self.version.save(update_fields=['effectivity_date'])
        PackageVersion.objects.create(
            title='V2',
            effectivity_date=timezone.now() - timedelta(days=1),
            company=self.supplier,
            account=self.account,
            is_active=False,
        )
        pkg = resolve_active_package_for_supplier_tier(self.supplier.id, self.tier.id)
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.id, self.package.id)
        self.assertEqual(pkg.package_version_id, self.version.id)

    def test_resolve_rejects_tier_not_on_supplier_company(self):
        other = Company.objects.create(
            account=self.account,
            name='Other co',
            supplier_type=SupplierType.objects.create(name='Zed'),
        )
        foreign_tier = Tier.objects.create(
            account=self.account,
            company=other,
            name='Silver',
        )
        self.assertIsNone(
            resolve_active_package_for_supplier_tier(self.supplier.id, foreign_tier.id),
        )


class SupplierBookingCapacityTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(name='Tenant', country=country)
        self.tenant_company = Company.objects.create(
            account=self.account,
            name='Tenant Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.supplier = Company.objects.create(
            account=self.account,
            name='Florist',
            supplier_type=supplier_type,
            max_bookings_per_day=1,
        )
        self.status = BookingStatus.objects.create(
            account=self.account,
            title='New',
        )
        self.event_day = timezone.datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc)
        self.group_name = 'Services'

    def _booking_with_supplier_line(self, *, supplier=None, when=None):
        supplier = supplier or self.supplier
        when = when or self.event_day
        booking = BookingItem.objects.create(
            account=self.account,
            company=self.tenant_company,
            status=self.status,
            unique_id='26-0099',
            title='Event',
            date_of_event=when,
        )
        group = BookingGroup.objects.create(booking=booking, name=self.group_name)
        BookingLine.objects.create(
            account=self.account,
            booking=booking,
            booking_group=group,
            company=supplier,
            label='Florist',
            field_type='supplier',
            value='',
        )
        return booking

    def _add_valid_payment(self, booking, **kwargs):
        defaults = {
            'account': self.account,
            'company': self.tenant_company,
            'amount': Decimal('100.00'),
            'tax': Decimal('0'),
            'transaction_status': 'succeeded',
            'transaction_id': 'txn_test',
        }
        defaults.update(kwargs)
        return BookingPayment.objects.create(booking=booking, **defaults)

    def test_unpaid_booking_does_not_count_toward_capacity(self):
        self._booking_with_supplier_line()
        status = supplier_booking_capacity_status(
            self.account.id,
            self.supplier.id,
            self.event_day.date(),
        )
        self.assertFalse(status['at_capacity'])
        self.assertEqual(status['booking_count'], 0)

    def test_at_capacity_when_paid_booking_reaches_max(self):
        booking = self._booking_with_supplier_line()
        self._add_valid_payment(booking)
        status = supplier_booking_capacity_status(
            self.account.id,
            self.supplier.id,
            self.event_day.date(),
        )
        self.assertTrue(status['at_capacity'])
        self.assertFalse(status['available'])
        self.assertEqual(status['booking_count'], 1)

    def test_exclude_current_booking_when_editing(self):
        booking = self._booking_with_supplier_line()
        self._add_valid_payment(booking)
        status = supplier_booking_capacity_status(
            self.account.id,
            self.supplier.id,
            self.event_day.date(),
            exclude_booking_id=booking.id,
        )
        self.assertFalse(status['at_capacity'])
        self.assertEqual(status['booking_count'], 0)

    def test_failed_payment_is_not_valid(self):
        booking = self._booking_with_supplier_line()
        payment = self._add_valid_payment(booking, transaction_status='failed')
        self.assertFalse(is_valid_booking_payment(payment))
        self.assertFalse(booking_has_valid_payment(booking.id))
