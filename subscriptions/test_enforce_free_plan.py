from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from countries.models import Country
from subscriptions.lifecycle import (
    enforce_free_plan_if_inactive_or_expired,
    resolve_account_subscription_for_account,
)
from subscriptions.models import AccountSubscription, Subscription
from users.models import Account


class EnforceFreePlanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.first()
        cls.free_monthly = Subscription.objects.filter(
            plan='free',
            billing_cycle='monthly',
        ).first()
        cls.pro_monthly = Subscription.objects.filter(
            plan='pro',
            billing_cycle='monthly',
        ).first()
        if cls.free_monthly is None or cls.pro_monthly is None or cls.country is None:
            cls.skip_setup = True
            return
        cls.skip_setup = False

    def setUp(self):
        if getattr(self, 'skip_setup', True):
            self.skipTest('Subscription seed data missing')
        self.account = Account.objects.create(
            name='Expired Sub Account',
            is_active=True,
            country=self.country,
        )

    def test_inactive_paid_plan_switches_to_free(self):
        today = timezone.localdate()
        AccountSubscription.objects.create(
            account=self.account,
            subscription=self.pro_monthly,
            status=AccountSubscription.Status.CANCELLED,
            team_seats=1,
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=10),
            base_price=Decimal('995'),
            total_per_users=Decimal('0'),
            total_price=Decimal('995'),
        )

        row, expired_plan = enforce_free_plan_if_inactive_or_expired(self.account.pk)
        row.refresh_from_db()

        self.assertEqual(expired_plan, 'pro')
        self.assertEqual(row.subscription.plan, 'free')
        self.assertEqual(row.status, AccountSubscription.Status.ACTIVE)

    def test_resolve_returns_expired_plan_slug_for_ui(self):
        today = timezone.localdate()
        AccountSubscription.objects.create(
            account=self.account,
            subscription=self.pro_monthly,
            status=AccountSubscription.Status.PAST_DUE,
            team_seats=1,
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=1),
            base_price=Decimal('995'),
            total_per_users=Decimal('0'),
            total_price=Decimal('995'),
        )

        row, expired_plan = resolve_account_subscription_for_account(self.account.pk)

        self.assertEqual(expired_plan, 'pro')
        self.assertEqual(row.subscription.plan, 'free')
        self.assertEqual(getattr(row, '_expired_paid_plan', None), 'pro')

    def test_active_expired_paid_plan_stays_selected_plan(self):
        today = timezone.localdate()
        AccountSubscription.objects.create(
            account=self.account,
            subscription=self.pro_monthly,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=1,
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=1),
            base_price=Decimal('995'),
            total_per_users=Decimal('0'),
            total_price=Decimal('995'),
        )

        row, expired_plan = resolve_account_subscription_for_account(self.account.pk)

        self.assertIsNone(expired_plan)
        self.assertEqual(row.subscription.plan, 'pro')
        self.assertEqual(row.status, AccountSubscription.Status.ACTIVE)
        self.assertTrue(row.end_date < today)
