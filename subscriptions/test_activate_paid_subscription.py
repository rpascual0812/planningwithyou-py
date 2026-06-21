from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from subscriptions.lifecycle import PREPAID_PERIOD_DAYS, activate_paid_subscription
from subscriptions.models import AccountSubscription, Subscription
from users.models import Account


class ActivatePaidSubscriptionTests(TestCase):
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
        self.account = Account.objects.create(name='Activate Test', is_active=True)

    def test_pending_subscription_becomes_active_with_30_day_period(self):
        today = timezone.localdate()
        row = AccountSubscription.objects.create(
            account=self.account,
            subscription=self.pro_monthly,
            status=AccountSubscription.Status.PENDING,
            team_seats=1,
            start_date=today - timedelta(days=5),
            end_date=None,
            base_price=Decimal('995'),
            total_per_users=Decimal('0'),
            total_price=Decimal('995'),
        )

        activate_paid_subscription(row)
        row.refresh_from_db()

        self.assertEqual(row.status, AccountSubscription.Status.ACTIVE)
        self.assertEqual(row.start_date, today)
        self.assertEqual(row.end_date, today + timedelta(days=PREPAID_PERIOD_DAYS))

    def test_active_expired_renewal_resets_dates_from_today(self):
        today = timezone.localdate()
        row = AccountSubscription.objects.create(
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

        activate_paid_subscription(row)
        row.refresh_from_db()

        self.assertEqual(row.status, AccountSubscription.Status.ACTIVE)
        self.assertEqual(row.start_date, today)
        self.assertEqual(row.end_date, today + timedelta(days=PREPAID_PERIOD_DAYS))
