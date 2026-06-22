import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.models import (
    Quotation,
    QuotationPayment,
    QuotationPaymentLink,
    QuotationStatus,
)
from companies.models import Company
from contacts.models import Contact
from countries.models import Country
from payments.models import WebhookLog
from suppliers.models import SupplierType
from users.models import Account, User
from users.registration import seed_company_defaults


def _payment_session_completed_payload(
    *,
    link: QuotationPaymentLink,
    payment_id: str = 'py-xendit-pl-webhook-1',
) -> dict:
    return {
        'event': 'payment_session.completed',
        'data': {
            'payment_session_id': link.xendit_payment_session_id,
            'reference_id': f'quote-link-{link.public_token}',
            'status': 'COMPLETED',
            'payment_id': payment_id,
            'session_type': 'PAY',
            'mode': 'PAYMENT_LINK',
        },
    }


@override_settings(XENDIT_WEBHOOK_TOKEN='xendit_pl_wh_test')
class XenditPaymentLinkWebhookViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence('accounts','id'), "
                "COALESCE((SELECT MAX(id) FROM accounts), 1))"
            )
        country = Country.objects.create(
            name='Testland PL WH',
            iso_code='TP9',
            iso2_code='Z9',
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
            unique_id='26-0600',
            title='Event',
            created_by=cls.user,
        )

    def setUp(self):
        token = uuid4()
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
            xendit_payment_session_id=f'ps-pl-wh-{token.hex[:8]}',
        )

    def _post_webhook(self, payload: dict, *, token: str = 'xendit_pl_wh_test'):
        raw = json.dumps(payload).encode('utf-8')
        return self.client.post(
            reverse('xendit-webhook'),
            data=raw,
            content_type='application/json',
            HTTP_X_CALLBACK_TOKEN=token,
        )

    @patch('bookings.payment_receipts.send_email_task.delay')
    def test_payment_session_completed_records_quotation_payment(self, _mock_email):
        response = self._post_webhook(_payment_session_completed_payload(link=self.link))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['handled'])

        payment = QuotationPayment.objects.get(transaction_id='py-xendit-pl-webhook-1')
        self.assertEqual(payment.transaction_status, 'paid')
        self.link.refresh_from_db()
        self.assertEqual(self.link.status, QuotationPaymentLink.Status.PAID)

        log = WebhookLog.objects.latest('created_at')
        self.assertEqual(log.source, 'xendit')
        self.assertTrue(log.handled)

    def test_invalid_callback_token_rejected(self):
        response = self._post_webhook(
            _payment_session_completed_payload(link=self.link),
            token='wrong-token',
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(QuotationPayment.objects.exists())

    def test_subscription_payload_without_matching_row_not_handled(self):
        payload = {
            'event': 'payment_session.completed',
            'data': {
                'payment_session_id': 'ps-sub-only',
                'reference_id': 'sub-checkout-ref-1',
                'status': 'COMPLETED',
                'payment_id': 'py-sub-only',
                'session_type': 'SUBSCRIPTION',
            },
        }
        response = self._post_webhook(payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['handled'])

    def test_payment_session_expired_marks_link_seen(self):
        payload = {
            'event': 'payment_session.expired',
            'data': {
                'payment_session_id': self.link.xendit_payment_session_id,
                'reference_id': f'quote-link-{self.link.public_token}',
                'status': 'EXPIRED',
            },
        }
        response = self._post_webhook(payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['handled'])
        self.assertFalse(QuotationPayment.objects.exists())
