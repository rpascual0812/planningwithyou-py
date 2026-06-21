import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from companies.models import Company
from payments.models import WebhookLog
from subscriptions.models import (
    AccountSubscription,
    Subscription,
    SubscriptionFailedPaymentNotice,
    SubscriptionPayment,
    SubscriptionReceipt,
)
from users.models import Account


def _payment_session_completed_payload(
    *,
    payment_session_id: str,
    reference_id: str = 'sub-checkout-ref-1',
    session_type: str = 'SUBSCRIPTION',
    status: str = 'COMPLETED',
    payment_id: str = 'py-xendit-webhook-test-1',
) -> dict:
    return {
        'event': 'payment_session.completed',
        'business_id': '661f87c614802d6c402cd82d',
        'created': '2026-12-31T23:59:59Z',
        'data': {
            'payment_session_id': payment_session_id,
            'reference_id': reference_id,
            'session_type': session_type,
            'status': status,
            'currency': 'PHP',
            'amount': 995,
            'payment_id': payment_id,
            'mode': 'PAYMENT_LINK',
        },
    }


@override_settings(XENDIT_WEBHOOK_TOKEN='xendit_wh_test')
class XenditSubscriptionWebhookTests(TestCase):
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
        self.account = Account.objects.create(name='Xendit Webhook Co', is_active=True)
        Company.objects.create(
            account=self.account,
            name='Xendit Webhook Co',
            is_active=True,
            is_main=True,
        )
        self.account_sub = AccountSubscription.objects.create(
            account=self.account,
            subscription=self.pro_monthly,
            status=AccountSubscription.Status.PENDING,
            team_seats=1,
            start_date=timezone.localdate(),
            end_date=None,
            base_price=Decimal('995'),
            total_per_users=Decimal('0'),
            total_price=Decimal('995'),
            reference_id='ps-xendit-webhook-test-1',
        )

    def _post_webhook(self, payload: dict, *, token: str = 'xendit_wh_test'):
        raw = json.dumps(payload).encode('utf-8')
        return self.client.post(
            reverse('xendit-webhook'),
            data=raw,
            content_type='application/json',
            HTTP_X_CALLBACK_TOKEN=token,
        )

    @patch('subscriptions.subscription_billing_notifications.send_email_task')
    @patch('subscriptions.subscription_billing_notifications.create_and_queue_email')
    def test_payment_session_completed_activates_pending_subscription(
        self,
        mock_create_email,
        mock_send_task,
    ):
        mock_create_email.return_value = type('Log', (), {'pk': 1})()
        payload = _payment_session_completed_payload(
            payment_session_id='ps-xendit-webhook-test-1',
            reference_id='sub-checkout-ref-1',
        )
        response = self._post_webhook(payload)

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['received'])
        self.assertTrue(data['handled'])

        self.account_sub.refresh_from_db()
        self.assertEqual(self.account_sub.status, AccountSubscription.Status.ACTIVE)
        self.assertIsNotNone(self.account_sub.end_date)

        payment = SubscriptionPayment.objects.get(
            paymongo_payment_id='py-xendit-webhook-test-1',
        )
        self.assertEqual(payment.amount, Decimal('995'))
        self.assertEqual(payment.paymongo_invoice_id, 'ps-xendit-webhook-test-1')
        self.assertEqual(SubscriptionReceipt.objects.filter(payment=payment).count(), 1)

        log = WebhookLog.objects.latest('created_at')
        self.assertEqual(log.source, 'xendit')
        self.assertTrue(log.handled)
        self.assertIsNotNone(log.processed_at)

    @patch('subscriptions.subscription_billing_notifications.send_email_task')
    @patch('subscriptions.subscription_billing_notifications.create_and_queue_email')
    def test_payment_session_completed_matches_checkout_reference_id(
        self,
        mock_create_email,
        mock_send_task,
    ):
        mock_create_email.return_value = type('Log', (), {'pk': 1})()
        checkout_ref = 'sub-checkout-ref-only'
        self.account_sub.reference_id = checkout_ref
        self.account_sub.save(update_fields=['reference_id', 'updated_at'])

        payload = _payment_session_completed_payload(
            payment_session_id='ps-new-session-id',
            reference_id=checkout_ref,
            payment_id='py-new-session-id',
        )
        response = self._post_webhook(payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['handled'])
        self.account_sub.refresh_from_db()
        self.assertEqual(self.account_sub.status, AccountSubscription.Status.ACTIVE)
        self.assertEqual(self.account_sub.reference_id, 'ps-new-session-id')
        self.assertTrue(
            SubscriptionPayment.objects.filter(
                paymongo_payment_id='py-new-session-id',
            ).exists(),
        )

    @patch('subscriptions.xendit_activation.retrieve_session')
    @patch('subscriptions.subscription_billing_notifications.send_email_task')
    @patch('subscriptions.subscription_billing_notifications.create_and_queue_email')
    def test_payment_session_completed_fetches_session_metadata_when_missing(
        self,
        mock_create_email,
        mock_send_task,
        mock_retrieve_session,
    ):
        mock_create_email.return_value = type('Log', (), {'pk': 1})()
        mock_retrieve_session.return_value = {
            'payment_session_id': 'ps-metadata-fetch',
            'status': 'COMPLETED',
            'session_type': 'PAY',
            'metadata': {
                'kind': 'subscription_plan_switch',
                'account_subscription_id': str(self.account_sub.pk),
                'subscription_id': str(self.pro_monthly.pk),
                'team_seats': '1',
            },
        }
        self.account_sub.reference_id = 'ps-metadata-fetch'
        self.account_sub.save(update_fields=['reference_id', 'updated_at'])

        payload = _payment_session_completed_payload(
            payment_session_id='ps-metadata-fetch',
            session_type='PAY',
            payment_id='py-metadata-fetch',
        )
        response = self._post_webhook(payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['handled'])
        mock_retrieve_session.assert_called_once_with('ps-metadata-fetch')
        self.account_sub.refresh_from_db()
        self.assertEqual(self.account_sub.status, AccountSubscription.Status.ACTIVE)
        self.assertTrue(
            SubscriptionPayment.objects.filter(
                paymongo_payment_id='py-metadata-fetch',
            ).exists(),
        )

    def test_invalid_callback_token_rejected(self):
        payload = _payment_session_completed_payload(
            payment_session_id='ps-xendit-webhook-test-1',
        )
        before_logs = WebhookLog.objects.count()
        response = self._post_webhook(payload, token='wrong-token')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(WebhookLog.objects.count(), before_logs + 1)
        log = WebhookLog.objects.latest('created_at')
        self.assertEqual(log.source, 'xendit')
        self.assertFalse(log.handled)
        self.assertEqual(log.error_message, 'Invalid callback token')
        self.account_sub.refresh_from_db()
        self.assertEqual(self.account_sub.status, AccountSubscription.Status.PENDING)
        self.assertEqual(SubscriptionPayment.objects.count(), 0)

    def test_non_completed_session_not_handled(self):
        payload = _payment_session_completed_payload(
            payment_session_id='ps-xendit-webhook-test-1',
            status='ACTIVE',
        )
        response = self._post_webhook(payload)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['handled'])
        log = WebhookLog.objects.latest('created_at')
        self.assertEqual(log.source, 'xendit')
        self.assertFalse(log.handled)
        self.account_sub.refresh_from_db()
        self.assertEqual(self.account_sub.status, AccountSubscription.Status.PENDING)
        self.assertEqual(SubscriptionPayment.objects.count(), 0)

    def test_unknown_event_logged_but_not_handled(self):
        payload = {
            'event': 'payment.capture',
            'data': {'payment_id': 'py-unknown'},
        }
        response = self._post_webhook(payload)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['handled'])
        log = WebhookLog.objects.latest('created_at')
        self.assertEqual(log.source, 'xendit')
        self.assertIsNotNone(log.processed_at)

    @patch('subscriptions.subscription_billing_notifications.send_email_task')
    @patch('subscriptions.subscription_billing_notifications.create_and_queue_email')
    def test_payment_session_expired_notifies_account(
        self,
        mock_create_email,
        mock_send_task,
    ):
        mock_create_email.return_value = type('Log', (), {'pk': 1})()
        self.account.contact_email = 'billing@xendit.test'
        self.account.save(update_fields=['contact_email'])

        payload = {
            'event': 'payment_session.expired',
            'data': {
                'payment_session_id': 'ps-xendit-webhook-test-1',
                'reference_id': 'sub-checkout-ref-1',
                'status': 'EXPIRED',
                'amount': 995,
            },
        }
        response = self._post_webhook(payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['handled'])
        notice = SubscriptionFailedPaymentNotice.objects.get(
            paymongo_invoice_id='xendit-ps-xendit-webhook-test-1-expired',
        )
        self.assertIsNotNone(notice.emailed_at)
        self.account_sub.refresh_from_db()
        self.assertEqual(self.account_sub.status, AccountSubscription.Status.PENDING)
        self.assertEqual(SubscriptionPayment.objects.count(), 0)
