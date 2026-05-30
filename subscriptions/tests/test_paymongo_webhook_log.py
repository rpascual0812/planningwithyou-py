import hashlib
import hmac
import json
import time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from companies.models import Company
from payments.models import WebhookLog
from unittest.mock import patch

from subscriptions.models import (
    AccountSubscription,
    Subscription,
    SubscriptionFailedPaymentNotice,
    SubscriptionPayment,
    SubscriptionReceipt,
)
from users.models import Account


def _paymongo_signature(payload: bytes, secret: str, *, live: bool = False) -> str:
    timestamp = str(int(time.time()))
    signed = f'{timestamp}.{payload.decode("utf-8")}'.encode('utf-8')
    digest = hmac.new(secret.encode('utf-8'), signed, hashlib.sha256).hexdigest()
    if live:
        return f't={timestamp},te=,li={digest}'
    return f't={timestamp},te={digest},li='


@override_settings(PAYMONGO_WEBHOOK_SECRET='whsec_sub_test')
class SubscriptionPayMongoWebhookLogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pro_monthly = Subscription.objects.filter(
            plan='pro',
            billing_cycle='monthly',
        ).first()
        if cls.pro_monthly is None:
            cls.skip_setup = True
            return
        cls.skip_setup = False

    def setUp(self):
        if getattr(self, 'skip_setup', True):
            self.skipTest('Subscription seed data missing')
        self.account = Account.objects.create(name='Webhook Co', is_active=True)
        Company.objects.create(
            account=self.account,
            name='Webhook Co',
            is_active=True,
            is_main=True,
        )
        self.account_sub = AccountSubscription.objects.create(
            account=self.account,
            subscription=self.pro_monthly,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=1,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            base_price=Decimal('995'),
            total_per_users=Decimal('0'),
            total_price=Decimal('995'),
            reference_id='sub_webhook_test_123',
        )

    def _post_webhook(self, payload: dict):
        raw = json.dumps(payload).encode('utf-8')
        return self.client.post(
            reverse('paymongo-webhook'),
            data=raw,
            content_type='application/json',
            HTTP_PAYMONGO_SIGNATURE=_paymongo_signature(raw, 'whsec_sub_test'),
        )

    def test_subscription_invoice_paid_logged_then_processed(self):
        payload = {
            'data': {
                'id': 'evt_sub_inv_1',
                'type': 'event',
                'attributes': {
                    'type': 'subscription.invoice.paid',
                    'data': {
                        'id': 'inv_test_1',
                        'type': 'subscription_invoice',
                        'attributes': {
                            'amount': 99500,
                            'subscription_id': 'sub_webhook_test_123',
                            'status': 'paid',
                            'next_billing_schedule': '2026-07-01',
                        },
                    },
                },
            },
        }
        before_logs = WebhookLog.objects.count()
        response = self._post_webhook(payload)

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['received'])
        self.assertTrue(data['handled'])
        self.assertEqual(WebhookLog.objects.count(), before_logs + 1)

        log = WebhookLog.objects.latest('created_at')
        self.assertEqual(log.source, 'paymongo')
        self.assertEqual(log.payload, payload)
        self.assertIsNotNone(log.processed_at)
        self.assertTrue(log.handled)
        self.assertEqual(log.error_message, '')

        self.assertTrue(
            SubscriptionPayment.objects.filter(
                paymongo_invoice_id='inv_test_1',
            ).exists(),
        )
        self.assertEqual(SubscriptionReceipt.objects.count(), 1)

    @patch('subscriptions.subscription_billing_notifications.send_email_task')
    @patch('subscriptions.subscription_billing_notifications.create_and_queue_email')
    def test_subscription_invoice_payment_failed_emails_contact(
        self,
        mock_create_email,
        mock_send_task,
    ):
        mock_create_email.return_value = type('Log', (), {'pk': 99})()
        self.account.contact_email = 'billing@webhook.test'
        self.account.save(update_fields=['contact_email'])

        payload = {
            'data': {
                'id': 'evt_sub_fail_1',
                'type': 'event',
                'attributes': {
                    'type': 'subscription.invoice.payment_failed',
                    'data': {
                        'id': 'inv_failed_1',
                        'type': 'subscription_invoice',
                        'attributes': {
                            'amount': 99500,
                            'subscription_id': 'sub_webhook_test_123',
                            'status': 'payment_failed',
                        },
                    },
                },
            },
        }
        response = self._post_webhook(payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['handled'])
        self.account_sub.refresh_from_db()
        self.assertEqual(self.account_sub.status, AccountSubscription.Status.PAST_DUE)

        notice = SubscriptionFailedPaymentNotice.objects.get(
            paymongo_invoice_id='inv_failed_1',
        )
        self.assertIsNotNone(notice.emailed_at)
        mock_create_email.assert_called_once()
        recipients = mock_create_email.call_args.kwargs.get('to') or []
        self.assertIn('billing@webhook.test', recipients)
        self.assertEqual(SubscriptionPayment.objects.count(), 0)
        self.assertEqual(SubscriptionReceipt.objects.count(), 0)

    def test_subscription_activated_does_not_create_receipt(self):
        payload = {
            'data': {
                'id': 'evt_sub_act',
                'type': 'event',
                'attributes': {
                    'type': 'subscription.activated',
                    'data': {
                        'id': 'sub_webhook_test_123',
                        'type': 'subscription',
                        'attributes': {
                            'status': 'active',
                            'next_billing_schedule': '2026-08-01',
                        },
                    },
                },
            },
        }
        response = self._post_webhook(payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['handled'])
        self.assertEqual(SubscriptionPayment.objects.count(), 0)
        self.assertEqual(SubscriptionReceipt.objects.count(), 0)

    def test_subscription_event_logged_when_account_unknown(self):
        payload = {
            'data': {
                'id': 'evt_sub_unknown',
                'type': 'event',
                'attributes': {
                    'type': 'subscription.activated',
                    'data': {
                        'id': 'sub_does_not_exist',
                        'type': 'subscription',
                        'attributes': {
                            'status': 'active',
                            'next_billing_schedule': '2026-07-01',
                        },
                    },
                },
            },
        }
        response = self._post_webhook(payload)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['handled'])

        log = WebhookLog.objects.latest('created_at')
        self.assertIsNotNone(log.processed_at)
        self.assertFalse(log.handled)
