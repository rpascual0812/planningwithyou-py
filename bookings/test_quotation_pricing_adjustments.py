from decimal import Decimal

from django.test import TestCase

from bookings.models import Quotation, QuotationLine, QuotationStatus
from bookings.quotation_pricing_adjustments import (
    apply_quotation_discount,
    resolve_quotation_effective_total,
    sum_quotation_line_subtotal,
    sync_quotation_total_amount,
)
from companies.models import Company
from users.models import Account, Country


class QuotationPricingAdjustmentsTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        self.account = Account.objects.create(name='Tenant', country=country)
        self.company = Company.objects.create(
            account=self.account,
            name='Co',
            is_main=True,
        )
        self.status = QuotationStatus.objects.create(
            account=self.account,
            company=self.company,
            title='Draft',
        )
        self.booking = Quotation.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='ABC1234',
            title='Event',
            total_amount=Decimal('0'),
        )
        QuotationLine.objects.create(
            quotation=self.booking,
            account=self.account,
            label='Package',
            field_type='number',
            price=Decimal('1000.00'),
            sort_order=0,
        )

    def test_line_subtotal_sums_priced_fields(self):
        self.assertEqual(sum_quotation_line_subtotal(self.booking), Decimal('1000.00'))

    def test_percent_discount_reduces_total(self):
        self.booking.discount_amount = Decimal('10')
        self.booking.discount_type = 'percent'
        self.assertEqual(
            resolve_quotation_effective_total(self.booking),
            Decimal('900.00'),
        )

    def test_override_total_replaces_subtotal(self):
        self.booking.total_override_amount = Decimal('750.00')
        self.assertEqual(
            resolve_quotation_effective_total(self.booking),
            Decimal('750.00'),
        )

    def test_sync_persists_effective_total(self):
        self.booking.discount_amount = Decimal('100')
        self.booking.discount_type = 'fixed'
        sync_quotation_total_amount(self.booking)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.total_amount, Decimal('900.00'))

    def test_apply_fixed_discount(self):
        self.assertEqual(
            apply_quotation_discount(Decimal('1000'), Decimal('250'), 'fixed'),
            Decimal('750.00'),
        )
