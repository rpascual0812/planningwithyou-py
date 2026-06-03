from decimal import Decimal

from django.test import TestCase

from bookings.models import Quotation, QuotationPayment
from companies.models import Company
from config.models import Country
from suppliers.models import SupplierType
from users.models import Account, User


class QuotationPaymentPayoutAdminTests(TestCase):
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
        from bookings.models import QuotationStatus

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
        )
        from users.test_support import grant_platform_admin

        self.admin = User.objects.create_user(
            username='admin-payout@test.com',
            email='admin-payout@test.com',
            password='test-pass',
            account=self.account,
            company=self.company,
        )
        grant_platform_admin(self.admin)
        self.user = User.objects.create_user(
            username='user-payout@test.com',
            email='user-payout@test.com',
            password='test-pass',
            account=self.account,
            company=self.company,
        )

    def test_admin_lists_valid_payments(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.get('/admin/quotation-payments/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['company_name'], 'Payout Co')
        self.assertFalse(res.data[0]['payout_sent'])

    def test_filter_pending_payouts(self):
        from rest_framework.test import APIClient

        self.payment.payout_sent_at = self.payment.created_at
        self.payment.save(update_fields=['payout_sent_at'])

        client = APIClient()
        client.force_authenticate(user=self.admin)
        pending = client.get('/admin/quotation-payments/', {'payout': 'pending'})
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(len(pending.data), 0)

        sent = client.get('/admin/quotation-payments/', {'payout': 'sent'})
        self.assertEqual(len(sent.data), 1)

    def test_mark_payout_sent(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.post(
            f'/admin/quotation-payments/{self.payment.pk}/mark-payout-sent/',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['payout_sent'])
        self.payment.refresh_from_db()
        self.assertIsNotNone(self.payment.payout_sent_at)

    def test_non_admin_forbidden(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get('/admin/quotation-payments/')
        self.assertEqual(res.status_code, 403)
