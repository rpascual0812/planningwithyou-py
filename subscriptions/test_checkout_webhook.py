from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bookings.paymongo_client import PayMongoError
from subscriptions.models import AccountSubscription, Subscription
from subscriptions.paymongo_checkout_webhook import (
    CHECKOUT_KIND_SEAT_UPGRADE,
    handle_subscription_checkout_webhook_event,
)
from users.models import Account


class SubscriptionCheckoutWebhookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company='Test Co')
        cls.monthly_pro = Subscription.objects.create(
            plan='pro',
            name='Pro',
            billing_cycle='monthly',
            base_price=Decimal('1000'),
            price_per_user=Decimal('100'),
            default_users=1,
            has_team_stepper=True,
        )
        cls.account_sub = AccountSubscription.objects.create(
            account=cls.account,
            subscription=cls.monthly_pro,
            status=AccountSubscription.Status.ACTIVE,
            reference_id='sub_paymongo_123',
            team_seats=2,
            start_date=timezone.localdate(),
            base_price=Decimal('1000'),
            total_per_users=Decimal('100'),
            total_price=Decimal('1100'),
        )

    def _checkout_event(self, team_seats: int = 3) -> dict:
        return {
            'type': 'checkout.session.completed',
            'data': {
                'attributes': {
                    'metadata': {
                        'kind': CHECKOUT_KIND_SEAT_UPGRADE,
                        'account_subscription_id': str(self.account_sub.pk),
                        'subscription_id': str(self.monthly_pro.pk),
                        'team_seats': str(team_seats),
                    },
                },
            },
        }

    @patch(
        'subscriptions.paymongo_subscriptions.update_account_subscription_recurring_plan',
        return_value=False,
    )
    def test_webhook_applies_db_even_when_paymongo_recurring_fails(self, _mock_update):
        handled = handle_subscription_checkout_webhook_event(self._checkout_event())
        self.assertTrue(handled)
        self.account_sub.refresh_from_db()
        self.assertEqual(self.account_sub.team_seats, 3)
        self.assertEqual(self.account_sub.total_price, Decimal('1200'))

    @patch('subscriptions.paymongo_subscriptions.create_subscription_plan')
    def test_webhook_does_not_raise_on_paymongo_plan_error(self, mock_create_plan):
        mock_create_plan.side_effect = PayMongoError(
            'no subscription payment methods are configured for this organization',
        )
        handled = handle_subscription_checkout_webhook_event(self._checkout_event())
        self.assertTrue(handled)
        self.account_sub.refresh_from_db()
        self.assertEqual(self.account_sub.team_seats, 3)
