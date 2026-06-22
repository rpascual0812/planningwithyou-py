from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from bookings.models import (
    Quotation,
    QuotationPayment,
    QuotationPaymentLink,
    QuotationStatus,
)
from bookings.xendit_booking_webhook import apply_xendit_booking_payment_session_completed
from companies.models import Company
from contacts.models import Contact
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account, User
from users.registration import seed_company_defaults


class XenditBookingWebhookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence('accounts','id'), "
                "COALESCE((SELECT MAX(id) FROM accounts), 1))"
            )
        country = Country.objects.create(
            name='Testland Xendit',
            iso_code='TXD',
            iso2_code='TX',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='Planner')
        cls.account = Account.objects.create(name='Tenant', country=country)
        cls.company = Company.objects.create(
            account=cls.account,
            name='Acme Events Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        seed_company_defaults(cls.account, cls.company)
        cls.status = QuotationStatus.objects.create(
            account=cls.account,
            company=cls.company,
            title='New',
        )
        cls.user = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='test-pass',
            account=cls.account,
            company=cls.company,
        )
        cls.contact = Contact.objects.create(
            account=cls.account,
            company_org=cls.company,
            first_name='Jane',
            last_name='Client',
            email='jane.client@example.com',
        )
        cls.booking = Quotation.objects.create(
            account=cls.account,
            company=cls.company,
            status=cls.status,
            contact=cls.contact,
            unique_id='26-0400',
            title='Wedding Reception',
            total_amount=Decimal('1500.00'),
            required_downpayment_amount=Decimal('500.00'),
            created_by=cls.user,
        )

    def setUp(self):
        token = uuid4()
        self.session_id = f'ps-xendit-{token.hex[:12]}'
        self.link = QuotationPaymentLink.objects.create(
            quotation=self.booking,
            account_id=self.account.id,
            company_id=self.company.id,
            public_token=token,
            base_amount=Decimal('500.00'),
            platform_fee=Decimal('5.00'),
            processing_fee_estimate=Decimal('20.00'),
            charge_amount=Decimal('525.00'),
            currency='PHP',
            status=QuotationPaymentLink.Status.PENDING,
            expires_at=timezone.now() + timedelta(days=7),
            payment_provider=QuotationPaymentLink.PaymentProvider.XENDIT,
            xendit_payment_session_id=self.session_id,
        )

    def test_ignores_non_booking_metadata(self):
        handled = apply_xendit_booking_payment_session_completed(
            {
                'status': 'COMPLETED',
                'payment_id': 'py-ignored',
                'metadata': {'kind': 'subscription'},
            },
        )
        self.assertFalse(handled)
        self.assertFalse(QuotationPayment.objects.filter(transaction_id='py-ignored').exists())

    def test_completed_session_without_metadata_records_payment_by_reference_id(self):
        handled = apply_xendit_booking_payment_session_completed(
            {
                'payment_session_id': self.session_id,
                'reference_id': f'quote-link-{self.link.public_token}',
                'status': 'COMPLETED',
                'payment_id': 'py-real-webhook-1',
            },
        )
        self.assertTrue(handled)
        payment = QuotationPayment.objects.get(transaction_id='py-real-webhook-1')
        self.assertEqual(payment.transaction_status, 'paid')
        self.assertEqual(payment.payment_method, 'xendit')
        self.link.refresh_from_db()
        self.assertEqual(self.link.status, QuotationPaymentLink.Status.PAID)

    def test_completed_session_without_metadata_records_payment_by_session_id(self):
        handled = apply_xendit_booking_payment_session_completed(
            {
                'payment_session_id': self.session_id,
                'status': 'COMPLETED',
                'payment_id': 'py-session-only-1',
            },
        )
        self.assertTrue(handled)
        payment = QuotationPayment.objects.get(transaction_id='py-session-only-1')
        self.assertEqual(payment.transaction_status, 'paid')
