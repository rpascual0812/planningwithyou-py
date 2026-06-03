from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import Quotation, QuotationPayment, QuotationStatus
from companies.models import Company
from contacts.models import Contact
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class ManualQuotationPaymentTests(TestCase):
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
        self.contact = Contact.objects.create(
            account=self.account,
            company=self.company,
            first_name='Pat',
            last_name='Lee',
            email='pat@example.com',
        )
        self.quotation = Quotation.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            contact=self.contact,
            unique_id='26-0100',
            title='Wedding',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch('bookings.manual_payments.notify_payment_received')
    def test_create_manual_payment(self, notify_mock):
        res = self.client.post(
            f'/quotation-items/{self.quotation.pk}/manual-payments/',
            {
                'amount': '250.50',
                'payment_method': 'Cash',
                'notes': 'Paid at office',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        payment = QuotationPayment.objects.get(quotation=self.quotation)
        self.assertEqual(payment.amount, Decimal('250.50'))
        self.assertEqual(payment.charge_amount, Decimal('250.50'))
        self.assertEqual(payment.base_amount, Decimal('250.50'))
        self.assertEqual(payment.net_amount, Decimal('250.50'))
        self.assertEqual(payment.platform_fee, Decimal('0'))
        self.assertEqual(payment.processing_fee, Decimal('0'))
        self.assertEqual(payment.payment_method, 'Cash')
        self.assertEqual(payment.transaction_status, 'paid')
        self.assertEqual(payment.notes, 'Paid at office')
        self.assertTrue(payment.transaction_id)
        self.assertIsNotNone(payment.payout_sent_at)
        notify_mock.assert_called_once()
        self.assertTrue(notify_mock.call_args.kwargs.get('use_contact_email'))
