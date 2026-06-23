from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from subscriptions.checkout import _xendit_use_subscription_checkout
from subscriptions.models import AccountSubscription, Subscription
from subscriptions.xendit_subscriptions import (
    _schedule_for_billing_cycle,
    create_subscription_checkout_session,
)


class XenditSubscriptionScheduleTests(TestCase):
    def test_monthly_schedule(self):
        schedule = _schedule_for_billing_cycle(Subscription.BillingCycle.MONTHLY)
        self.assertEqual(schedule['interval'], 'MONTH')
        self.assertEqual(schedule['interval_count'], 1)

    def test_yearly_schedule(self):
        schedule = _schedule_for_billing_cycle(Subscription.BillingCycle.YEARLY)
        self.assertEqual(schedule['interval'], 'MONTH')
        self.assertEqual(schedule['interval_count'], 12)


class XenditSubscriptionCheckoutSelectionTests(TestCase):
    def _account_sub(self, *, reference_id: str = '') -> AccountSubscription:
        account_sub = AccountSubscription(reference_id=reference_id)
        return account_sub

    def test_full_subscription_always_uses_recurring_session(self):
        self.assertTrue(
            _xendit_use_subscription_checkout(
                checkout_kind='full_subscription',
                charge_now=Decimal('500'),
                full_price=Decimal('995'),
                account_sub=self._account_sub(),
            ),
        )

    def test_prorated_plan_switch_without_reference_uses_recurring_session(self):
        self.assertTrue(
            _xendit_use_subscription_checkout(
                checkout_kind='plan_change_proration',
                charge_now=Decimal('500'),
                full_price=Decimal('995'),
                account_sub=self._account_sub(),
            ),
        )

    def test_prorated_plan_switch_with_reference_uses_one_time(self):
        self.assertFalse(
            _xendit_use_subscription_checkout(
                checkout_kind='plan_change_proration',
                charge_now=Decimal('500'),
                full_price=Decimal('995'),
                account_sub=self._account_sub(reference_id='repl-123'),
            ),
        )


@override_settings(XENDIT_SECRET_KEY='test-secret')
class XenditCreateSubscriptionCheckoutSessionTests(TestCase):
    def setUp(self):
        self.user = MagicMock()
        self.user.email = 'xendit-api@example.com'
        self.user.first_name = 'Test'
        self.user.last_name = 'User'

    @patch('subscriptions.xendit_subscriptions._request')
    def test_create_monthly_subscription_session_payload(self, mock_request):
        mock_request.return_value = {
            'payment_session_id': 'ps-test-monthly',
            'payment_link_url': 'https://checkout.xendit.co/sessions/ps-test-monthly',
        }
        create_subscription_checkout_session(
            account_id=42,
            user=self.user,
            billing_email='xendit-api@example.com',
            reference_id='sub-test-monthly',
            description='Pro monthly',
            amount_php=Decimal('995'),
            billing_cycle=Subscription.BillingCycle.MONTHLY,
            success_url='https://app.example.com/success',
            cancel_url='https://app.example.com/cancel',
            metadata={'kind': 'account_subscription'},
        )
        body = mock_request.call_args.args[2]
        self.assertEqual(body['session_type'], 'SUBSCRIPTION')
        self.assertEqual(body['amount'], 995.0)
        self.assertEqual(body['subscription']['schedule']['interval'], 'MONTH')
        self.assertEqual(body['subscription']['schedule']['interval_count'], 1)
        self.assertIn('anchor_date', body['subscription']['schedule'])

    @patch('subscriptions.xendit_subscriptions._request')
    def test_create_yearly_subscription_session_payload(self, mock_request):
        mock_request.return_value = {
            'payment_session_id': 'ps-test-yearly',
            'payment_link_url': 'https://checkout.xendit.co/sessions/ps-test-yearly',
        }
        create_subscription_checkout_session(
            account_id=42,
            user=self.user,
            billing_email='xendit-api@example.com',
            reference_id='sub-test-yearly',
            description='Pro yearly',
            amount_php=Decimal('9995'),
            billing_cycle=Subscription.BillingCycle.YEARLY,
            success_url='https://app.example.com/success',
            cancel_url='https://app.example.com/cancel',
            metadata={'kind': 'account_subscription'},
        )
        body = mock_request.call_args.args[2]
        self.assertEqual(body['session_type'], 'SUBSCRIPTION')
        self.assertEqual(body['subscription']['schedule']['interval'], 'MONTH')
        self.assertEqual(body['subscription']['schedule']['interval_count'], 12)
