from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase
from django.utils import timezone

from subscriptions.lifecycle import should_offer_subscription_renewal
from subscriptions.models import AccountSubscription, Subscription


class ShouldOfferRenewalTests(SimpleTestCase):
    def _paid_row(
        self,
        *,
        plan: str = 'pro',
        status: str = AccountSubscription.Status.ACTIVE,
        end_date: date | None,
        row_plan: str | None = None,
    ) -> AccountSubscription:
        catalog = Subscription(
            pk=1,
            plan=plan,
            billing_cycle=Subscription.BillingCycle.MONTHLY,
        )
        row = AccountSubscription(
            subscription=Subscription(
                pk=2,
                plan=row_plan or plan,
                billing_cycle=Subscription.BillingCycle.MONTHLY,
            ),
            status=status,
            end_date=end_date,
            reference_id='sub_test',
            team_seats=1,
        )
        row.subscription = row.subscription  # noqa: B018
        return row

    def test_expired_yesterday_offers_renewal(self):
        today = timezone.localdate()
        row = self._paid_row(end_date=today - timedelta(days=1))
        target = Subscription(plan='pro', billing_cycle=Subscription.BillingCycle.MONTHLY)
        self.assertTrue(should_offer_subscription_renewal(row, target))

    def test_end_date_today_offers_renewal(self):
        today = timezone.localdate()
        row = self._paid_row(end_date=today)
        target = Subscription(plan='pro', billing_cycle=Subscription.BillingCycle.MONTHLY)
        self.assertTrue(should_offer_subscription_renewal(row, target))

    def test_future_end_date_requires_renew_expired_flag(self):
        today = timezone.localdate()
        row = self._paid_row(end_date=today + timedelta(days=10))
        target = Subscription(plan='pro', billing_cycle=Subscription.BillingCycle.MONTHLY)
        self.assertFalse(should_offer_subscription_renewal(row, target))
        self.assertFalse(should_offer_subscription_renewal(row, target, renew_expired=True))

    def test_free_row_with_expired_paid_plan(self):
        today = timezone.localdate()
        row = self._paid_row(plan='free', row_plan='free', end_date=None)
        row._expired_paid_plan = 'pro'  # noqa: SLF001
        target = Subscription(plan='pro', billing_cycle=Subscription.BillingCycle.MONTHLY)
        self.assertTrue(should_offer_subscription_renewal(row, target))

    def test_active_future_period_does_not_offer_renewal(self):
        today = timezone.localdate()
        row = self._paid_row(end_date=today + timedelta(days=20))
        target = Subscription(plan='pro', billing_cycle=Subscription.BillingCycle.MONTHLY)
        self.assertFalse(should_offer_subscription_renewal(row, target))
