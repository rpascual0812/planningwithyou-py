from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from countries.models import Country

from subscriptions.checkout import resolve_checkout_quote, start_subscription_checkout
from subscriptions.errors import SubscriptionCheckoutError
from subscriptions.models import AccountSubscription, Subscription
from users.models import Account, User


class ExpiredRenewalCheckoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.first()
        if cls.country is None:
            cls.skip_setup = True
            return
        cls.skip_setup = False
        cls.account = Account.objects.create(
            name='Expired Renewal Co',
            contact_email='expired@example.com',
            country=cls.country,
        )
        cls.user = User.objects.create_user(
            username='expired@example.com',
            email='expired@example.com',
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

    def setUp(self):
        if getattr(self, 'skip_setup', True):
            self.skipTest('Country seed data missing')
        today = timezone.localdate()
        self.account_sub = AccountSubscription.objects.create(
            account=self.account,
            subscription=self.monthly_pro,
            status=AccountSubscription.Status.ACTIVE,
            reference_id='sub_paymongo_expired',
            team_seats=2,
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=1),
            base_price=Decimal('1000'),
            total_per_users=Decimal('100'),
            total_price=Decimal('1100'),
        )

    @patch('subscriptions.checkout.paymongo_configured', return_value=True)
    def test_expired_same_plan_preview_is_full_subscription(self, _mock_paymongo_configured):
        quote = resolve_checkout_quote(
            account=self.account,
            subscription=self.monthly_pro,
            team_seats=2,
        )
        self.assertEqual(quote.checkout_kind, 'full_subscription')
        self.assertGreater(quote.amount_due_now, Decimal('0'))
        self.assertTrue(quote.is_one_time_payment)

    @patch('subscriptions.checkout.paymongo_configured', return_value=True)
    @patch('subscriptions.checkout._collect_plan_switch_payment')
    def test_expired_same_plan_checkout_starts_renewal(
        self,
        mock_collect_payment,
        _mock_paymongo_configured,
    ):
        mock_collect_payment.return_value = {
            'checkout_kind': 'full_subscription',
            'amount': '1100',
            'checkout_url': 'https://checkout.example/renew',
        }

        result = start_subscription_checkout(
            account=self.account,
            user=self.user,
            subscription=self.monthly_pro,
            team_seats=2,
        )

        self.assertEqual(result['checkout_kind'], 'full_subscription')
        mock_collect_payment.assert_called_once()

    @patch('subscriptions.checkout.paymongo_configured', return_value=True)
    def test_expired_same_plan_does_not_raise_no_changes(self, _mock_paymongo_configured):
        try:
            resolve_checkout_quote(
                account=self.account,
                subscription=self.monthly_pro,
                team_seats=2,
            )
        except SubscriptionCheckoutError as exc:
            self.fail(f'Unexpected checkout error: {exc}')
