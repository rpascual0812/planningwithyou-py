from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from subscriptions.checkout import resolve_checkout_quote, start_subscription_checkout
from subscriptions.paymongo_subscriptions import update_account_subscription_recurring_plan
from subscriptions.models import AccountSubscription, Subscription
from users.models import Account, User


class PlanChangeCheckoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(
            company='Test Co',
            contact_email='billing@example.com',
        )
        cls.user = User.objects.create_user(
            username='billing@example.com',
            email='billing@example.com',
            password='test-pass',
            account=cls.account,
        )
        cls.monthly_pro = Subscription.objects.create(
            plan='pro',
            name='Pro',
            billing_cycle='monthly',
            base_price=Decimal('1000'),
            price_per_user=Decimal('100'),
            default_users=1,
            has_team_stepper=True,
        )
        cls.monthly_ai = Subscription.objects.create(
            plan='ai',
            name='AI',
            billing_cycle='monthly',
            base_price=Decimal('2000'),
            price_per_user=Decimal('200'),
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

    @patch('subscriptions.checkout.paymongo_configured', return_value=True)
    @patch('subscriptions.paymongo_subscriptions.change_subscription_plan')
    @patch('subscriptions.paymongo_subscriptions.create_subscription_plan')
    def test_plan_change_updates_paymongo_recurring(
        self,
        mock_create_plan,
        mock_change_plan,
        _mock_paymongo_configured,
    ):
        mock_create_plan.return_value = {'id': 'plan_new_456'}
        mock_change_plan.return_value = {'id': 'sub_paymongo_123'}

        result = start_subscription_checkout(
            account=self.account,
            user=self.user,
            subscription=self.monthly_ai,
            team_seats=2,
        )

        self.assertEqual(result['checkout_kind'], 'plan_change_only')
        self.assertEqual(result['amount'], '0')
        self.assertEqual(result['checkout_url'], '')
        self.assertEqual(result['paymongo_subscription_id'], 'sub_paymongo_123')

        self.account_sub.refresh_from_db()
        self.assertEqual(self.account_sub.subscription_id, self.monthly_ai.pk)
        self.assertEqual(self.account_sub.total_price, Decimal('2200'))

        mock_create_plan.assert_called_once()
        mock_change_plan.assert_called_once_with(
            subscription_id='sub_paymongo_123',
            plan_id='plan_new_456',
        )
        plan_attrs = mock_create_plan.call_args.kwargs
        self.assertEqual(plan_attrs['amount_php'], Decimal('2200'))
        self.assertEqual(plan_attrs['billing_cycle'], 'monthly')

    @patch('subscriptions.checkout.paymongo_configured', return_value=True)
    def test_plan_change_preview_no_payment_due_now(self, _mock_paymongo_configured):
        quote = resolve_checkout_quote(
            account=self.account,
            subscription=self.monthly_ai,
            team_seats=2,
        )
        self.assertEqual(quote.checkout_kind, 'plan_change_only')
        self.assertEqual(quote.amount_due_now, Decimal('0'))
        self.assertFalse(quote.is_one_time_payment)
        self.assertEqual(quote.next_billing_amount, Decimal('2200'))

    @patch('subscriptions.paymongo_subscriptions.create_subscription_plan')
    def test_update_paymongo_skips_without_reference(self, mock_create_plan):
        self.account_sub.reference_id = ''
        self.account_sub.save(update_fields=['reference_id', 'updated_at'])
        updated = update_account_subscription_recurring_plan(
            self.account_sub,
            self.monthly_ai,
            team_seats=2,
        )
        self.assertFalse(updated)
        mock_create_plan.assert_not_called()
