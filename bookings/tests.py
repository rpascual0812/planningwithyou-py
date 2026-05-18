from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bookings.models import BookingGroup, BookingItem, BookingLine, BookingStatus
from bookings.pdf_build import (
    _currency_for_account,
    _ensure_pdf_unicode_fonts,
    _format_money,
)
from bookings.pricing import resolve_booking_line_price
from bookings.unique_id import allocate_booking_unique_id, format_booking_unique_id
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account


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
            supplier_type=supplier_type,
        )

    def test_format_booking_unique_id(self):
        self.assertEqual(format_booking_unique_id(2026, 1), '26-0001')
        self.assertEqual(format_booking_unique_id(2026, 42), '26-0042')

    def test_allocate_increments_per_account_and_year(self):
        when = timezone.datetime(2026, 3, 15, tzinfo=timezone.utc)
        first = allocate_booking_unique_id(self.account.id, when=when)
        second = allocate_booking_unique_id(self.account.id, when=when)
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
            supplier_type=supplier_type,
        )
        self.status = BookingStatus.objects.create(
            account=self.account,
            title='New',
        )
        self.booking = BookingItem.objects.create(
            account=self.account,
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
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(
            name='PH Account',
            country=self.philippines,
            supplier_type=supplier_type,
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
