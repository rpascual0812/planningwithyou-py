"""Prorated charges for subscription seat upgrades."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .models import AccountSubscription, Subscription
from .pricing import MONTHS_BILLED_YEARLY, compute_subscription_pricing

TWOPLACES = Decimal('0.01')
MIN_CHECKOUT_PHP = Decimal('20.00')


def add_months(from_date: date, months: int) -> date:
    month = from_date.month - 1 + months
    year = from_date.year + month // 12
    month = month % 12 + 1
    day = min(
        from_date.day,
        calendar.monthrange(year, month)[1],
    )
    return date(year, month, day)


def add_years(from_date: date, years: int) -> date:
    try:
        return from_date.replace(year=from_date.year + years)
    except ValueError:
        return from_date.replace(year=from_date.year + years, day=28)


def billing_period_end(account_sub: AccountSubscription) -> date:
    if account_sub.end_date:
        return account_sub.end_date
    start = account_sub.start_date
    if account_sub.subscription.billing_cycle == Subscription.BillingCycle.YEARLY:
        return add_years(start, 1)
    return add_months(start, 1)


def per_user_amount_for_cycle(subscription: Subscription) -> Decimal:
    """Additional-user rate for one seat over the full billing period."""
    per_user = Decimal(subscription.price_per_user)
    if subscription.billing_cycle == Subscription.BillingCycle.YEARLY:
        return per_user * MONTHS_BILLED_YEARLY
    return per_user


@dataclass(frozen=True)
class SeatUpgradeProration:
    current_seats: int
    new_seats: int
    additional_seats: int
    period_start: date
    period_end: date
    days_remaining: int
    days_in_period: int
    proration_factor: Decimal
    per_user_period_amount: Decimal
    amount: Decimal


def compute_seat_upgrade_proration(
    *,
    subscription: Subscription,
    current_seats: int,
    new_seats: int,
    period_start: date,
    period_end: date,
    as_of: date | None = None,
) -> SeatUpgradeProration:
    today = as_of or timezone.localdate()
    additional = max(0, new_seats - current_seats)
    per_user = per_user_amount_for_cycle(subscription)
    days_in_period = max((period_end - period_start).days, 1)
    days_remaining = max((period_end - today).days, 0)
    factor = (
        Decimal(days_remaining) / Decimal(days_in_period)
        if days_remaining > 0
        else Decimal('0')
    )
    raw = per_user * additional * factor
    amount = raw.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return SeatUpgradeProration(
        current_seats=current_seats,
        new_seats=new_seats,
        additional_seats=additional,
        period_start=period_start,
        period_end=period_end,
        days_remaining=days_remaining,
        days_in_period=days_in_period,
        proration_factor=factor,
        per_user_period_amount=per_user,
        amount=amount,
    )


def compute_remaining_period_credit(
    account_sub: AccountSubscription,
    as_of: date | None = None,
) -> Decimal:
    """Unused prepaid value on the current subscription period."""
    if account_sub.subscription.plan == 'free':
        return Decimal('0')
    if account_sub.status != AccountSubscription.Status.ACTIVE:
        return Decimal('0')
    prepaid = account_sub.total_price or Decimal('0')
    if prepaid <= 0:
        return Decimal('0')
    today = as_of or timezone.localdate()
    period_end = billing_period_end(account_sub)
    if period_end <= today:
        return Decimal('0')
    period_start = account_sub.start_date
    days_in_period = max((period_end - period_start).days, 1)
    days_remaining = max((period_end - today).days, 0)
    if days_remaining <= 0:
        return Decimal('0')
    factor = Decimal(days_remaining) / Decimal(days_in_period)
    return (prepaid * factor).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def compute_plan_switch_checkout(
    *,
    account_sub: AccountSubscription | None,
    subscription: Subscription,
    team_seats: int,
    as_of: date | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Return (amount_due_now, full_recurring_amount, credit_applied).
    Recurring billing should always use full_recurring_amount.
    """
    pricing = compute_subscription_pricing(subscription, team_seats)
    full_price = pricing.total_price
    credit = (
        compute_remaining_period_credit(account_sub, as_of=as_of)
        if account_sub is not None
        else Decimal('0')
    )
    due_now = max(full_price - credit, Decimal('0'))
    due_now = checkout_amount_for_proration(due_now)
    return due_now, full_price, credit


def checkout_amount_for_proration(amount: Decimal) -> Decimal:
    """Enforce PayMongo minimum; zero stays zero."""
    if amount <= 0:
        return Decimal('0')
    if amount < MIN_CHECKOUT_PHP:
        return MIN_CHECKOUT_PHP
    return amount


def apply_subscription_selection(
    account_sub: AccountSubscription,
    subscription: Subscription,
    team_seats: int,
) -> None:
    """Persist plan/cycle/seat selection on the account subscription row."""
    pricing = compute_subscription_pricing(subscription, team_seats)
    account_sub.subscription = subscription
    account_sub.team_seats = pricing.team_seats
    account_sub.base_price = pricing.base_price
    account_sub.total_per_users = pricing.total_per_users
    account_sub.total_price = pricing.total_price
    account_sub.save(
        update_fields=[
            'subscription',
            'team_seats',
            'base_price',
            'total_per_users',
            'total_price',
            'updated_at',
        ],
    )


def apply_pricing_to_account_subscription(
    account_sub: AccountSubscription,
    subscription: Subscription,
    team_seats: int,
) -> None:
    apply_subscription_selection(account_sub, subscription, team_seats)


def same_plan_and_cycle(
    account_sub: AccountSubscription,
    subscription: Subscription,
) -> bool:
    return (
        account_sub.subscription_id == subscription.pk
        or (
            account_sub.subscription.plan == subscription.plan
            and account_sub.subscription.billing_cycle == subscription.billing_cycle
        )
    )
