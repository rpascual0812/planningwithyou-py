from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import Quotation, QuotationPayment, QuotationStatus
from bookings.payment_breakdown import (
    booking_payment_summary,
    booking_payments_paid_base_total,
)
from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class ManualQuotationRefundTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        supplier_type = SupplierType.objects.create(name='Planner')
        self.account = Account.objects.create(
            name='Acct',
            country=country,
            is_active=True,
        )
        self.company = Company.objects.create(
            account=self.account,
            name='Co',
            supplier_type=supplier_type,
            is_main=True,
            is_active=True,
        )
        self.user = User.objects.create_user(
            username='owner@test.com',
            email='owner@test.com',
            password='pass',
            account=self.account,
            company=self.company,
        )
        self.status = QuotationStatus.objects.create(
            account=self.account,
            company=self.company,
            title='New',
            sort_order=0,
        )
        self.quotation = Quotation.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0100',
            title='Wedding',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch('bookings.manual_payments.notify_payment_received')
    def test_create_manual_refund_reduces_paid_total(self, notify_mock):
        QuotationPayment.objects.create(
            quotation=self.quotation,
            account=self.account,
            company=self.company,
            base_amount=Decimal('500.00'),
            amount=Decimal('500.00'),
            charge_amount=Decimal('500.00'),
            net_amount=Decimal('500.00'),
            transaction_status='paid',
        )
        res = self.client.post(
            f'/quotation-items/{self.quotation.pk}/manual-refunds/',
            {
                'amount': '200.00',
                'payment_method': 'Bank Transfer',
                'notes': 'Partial refund',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        refund = QuotationPayment.objects.filter(
            quotation=self.quotation,
            transaction_status='refunded',
        ).get()
        self.assertEqual(refund.base_amount, Decimal('200.00'))
        self.assertEqual(refund.notes, 'Partial refund')
        self.assertIsNone(refund.payout_sent_at)
        notify_mock.assert_not_called()
        self.assertEqual(
            booking_payments_paid_base_total(self.quotation.pk),
            Decimal('300.00'),
        )
        summary = booking_payment_summary(self.quotation)
        self.assertEqual(summary['refunded_amount'], '200.00')
        self.assertEqual(summary['paid_amount'], '300.00')

    def test_create_refund_via_manual_payments_kind(self):
        QuotationPayment.objects.create(
            quotation=self.quotation,
            account=self.account,
            company=self.company,
            base_amount=Decimal('500.00'),
            amount=Decimal('500.00'),
            charge_amount=Decimal('500.00'),
            net_amount=Decimal('500.00'),
            transaction_status='paid',
        )
        res = self.client.post(
            f'/quotation-items/{self.quotation.pk}/manual-payments/',
            {
                'kind': 'refund',
                'amount': '50.00',
                'payment_method': 'Cash',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['transaction_status'], 'refunded')

    def test_refund_cannot_exceed_paid(self):
        QuotationPayment.objects.create(
            quotation=self.quotation,
            account=self.account,
            company=self.company,
            base_amount=Decimal('100.00'),
            amount=Decimal('100.00'),
            charge_amount=Decimal('100.00'),
            net_amount=Decimal('100.00'),
            transaction_status='paid',
        )
        res = self.client.post(
            f'/quotation-items/{self.quotation.pk}/manual-refunds/',
            {
                'amount': '150.00',
                'payment_method': 'Cash',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400)
