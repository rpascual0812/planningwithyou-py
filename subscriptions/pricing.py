"""Compute account subscription totals (matches SubscriptionSettingsPage)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import Subscription

MONTHS_BILLED_YEARLY = 10


@dataclass(frozen=True)
class SubscriptionPricing:
    team_seats: int
    users: int
    base_price: Decimal
    total_per_users: Decimal
    total_price: Decimal


def plan_users(subscription: Subscription, team_seats: int) -> int:
    if subscription.has_team_stepper:
        return max(1, team_seats)
    return subscription.default_users


def compute_monthly_total(subscription: Subscription, users: int) -> Decimal:
    base = Decimal(subscription.base_price)
    per_user = Decimal(subscription.price_per_user)
    if users <= 1:
        return base
    return base + per_user * (users - 1)


def compute_billed_amount(subscription: Subscription, team_seats: int) -> Decimal:
    users = plan_users(subscription, team_seats)
    monthly = compute_monthly_total(subscription, users)
    if subscription.billing_cycle == Subscription.BillingCycle.YEARLY:
        return monthly * MONTHS_BILLED_YEARLY
    return monthly


def compute_subscription_pricing(
    subscription: Subscription,
    team_seats: int,
) -> SubscriptionPricing:
    users = plan_users(subscription, team_seats)
    monthly = compute_monthly_total(subscription, users)
    cycle_multiplier = (
        MONTHS_BILLED_YEARLY
        if subscription.billing_cycle == Subscription.BillingCycle.YEARLY
        else 1
    )
    base_component = Decimal(subscription.base_price) * cycle_multiplier
    additional_users = max(0, users - 1)
    per_user_component = (
        Decimal(subscription.price_per_user) * additional_users * cycle_multiplier
    )
    total = compute_billed_amount(subscription, team_seats)
    return SubscriptionPricing(
        team_seats=team_seats if subscription.has_team_stepper else users,
        users=users,
        base_price=base_component,
        total_per_users=per_user_component,
        total_price=total,
    )
