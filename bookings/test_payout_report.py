from decimal import Decimal

from django.test import TestCase

from bookings.models import Quotation, QuotationPayment, QuotationStatus
from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account, User


class QuotationPaymentPayoutReportTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(name='Tenant', country=country)
        self.company = Company.objects.create(
            account=self.account,
            name='Payout Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.other_company = Company.objects.create(
            account=self.account,
            name='Other Co',
            supplier_type=supplier_type,
        )
        self.status = QuotationStatus.objects.create(
            account=self.account,
            company=self.company,
            title='New',
            sort_order=0,
        )
        self.booking = Quotation.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0100',
            title='Wedding',
        )
        self.payment = QuotationPayment.objects.create(
            quotation=self.booking,
            account=self.account,
            company=self.company,
            base_amount=Decimal('5000.00'),
            amount=Decimal('5000.00'),
            transaction_status='paid',
            transaction_id='pay_abc',
            notes='Deposit via bank',
        )
        QuotationPayment.objects.create(
            quotation=self.booking,
            account=self.account,
            company=self.other_company,
            base_amount=Decimal('100.00'),
            amount=Decimal('100.00'),
            transaction_status='paid',
            transaction_id='pay_other',
        )
        self.user = User.objects.create_user(
            username='user-payout@test.com',
            email='user-payout@test.com',
            password='test-pass',
            account=self.account,
            company=self.company,
        )

    def test_lists_payments_for_user_company_only(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get('/booking-payouts/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['quotation_unique_id'], '26-0100')
        self.assertEqual(res.data[0]['quotation_credit'], '5000.00')
        self.assertEqual(res.data[0]['notes'], 'Deposit via bank')

    def test_filter_pending_payouts(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        pending = client.get('/booking-payouts/', {'payout': 'pending'})
        self.assertEqual(len(pending.data), 1)

        self.payment.payout_sent_at = self.payment.created_at
        self.payment.save(update_fields=['payout_sent_at'])

        pending = client.get('/booking-payouts/', {'payout': 'pending'})
        self.assertEqual(len(pending.data), 0)

        sent = client.get('/booking-payouts/', {'payout': 'sent'})
        self.assertEqual(len(sent.data), 1)
