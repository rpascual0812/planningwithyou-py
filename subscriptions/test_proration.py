from datetime import date
from decimal import Decimal

from django.test import TestCase

from django.utils import timezone

from subscriptions.models import AccountSubscription, Subscription
from subscriptions.proration import (
    compute_plan_switch_checkout,
    compute_remaining_period_credit,
    compute_seat_upgrade_proration,
    per_user_amount_for_cycle,
)


class ProrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.monthly_pro = Subscription.objects.create(
            plan='pro',
            name='Pro',
            billing_cycle='monthly',
            base_price=Decimal('1000'),
            price_per_user=Decimal('100'),
            default_users=1,
            has_team_stepper=True,
        )

    def test_per_user_monthly_rate(self):
        self.assertEqual(
            per_user_amount_for_cycle(self.monthly_pro),
            Decimal('100'),
        )

    def test_proration_half_month_one_extra_seat(self):
        period_start = date(2026, 1, 1)
        period_end = date(2026, 2, 1)
        as_of = date(2026, 1, 16)
        result = compute_seat_upgrade_proration(
            subscription=self.monthly_pro,
            current_seats=2,
            new_seats=3,
            period_start=period_start,
            period_end=period_end,
            as_of=as_of,
        )
        self.assertEqual(result.additional_seats, 1)
        self.assertGreater(result.amount, Decimal('0'))
        self.assertLess(result.amount, Decimal('100'))

    def test_proration_zero_when_period_ended(self):
        result = compute_seat_upgrade_proration(
            subscription=self.monthly_pro,
            current_seats=1,
            new_seats=3,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 2, 1),
            as_of=date(2026, 3, 1),
        )
        self.assertEqual(result.amount, Decimal('0'))

    def test_remaining_period_credit_half_month(self):
        account = AccountSubscription(
            subscription=self.monthly_pro,
            status=AccountSubscription.Status.ACTIVE,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1),
            total_price=Decimal('1100'),
        )
        credit = compute_remaining_period_credit(account, as_of=date(2026, 1, 16))
        self.assertGreater(credit, Decimal('0'))
        self.assertLess(credit, Decimal('1100'))

    def test_pending_subscription_has_no_remaining_credit(self):
        account = AccountSubscription(
            subscription=self.monthly_pro,
            status=AccountSubscription.Status.PENDING,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1),
            total_price=Decimal('1100'),
        )
        credit = compute_remaining_period_credit(account, as_of=date(2026, 1, 16))
        self.assertEqual(credit, Decimal('0'))

    def test_pending_checkout_charges_full_price(self):
        account = AccountSubscription(
            subscription=self.monthly_pro,
            status=AccountSubscription.Status.PENDING,
            start_date=date(2026, 1, 1),
            end_date=None,
            total_price=Decimal('1100'),
            team_seats=1,
        )
        due_now, full_price, credit = compute_plan_switch_checkout(
            account_sub=account,
            subscription=self.monthly_pro,
            team_seats=1,
        )
        self.assertEqual(credit, Decimal('0'))
        self.assertEqual(due_now, full_price)
        self.assertGreater(due_now, Decimal('0'))
