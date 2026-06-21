"""Resolve subscription plan slugs from the single account_subscriptions row."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .lifecycle import (
    get_account_subscription_row,
    is_expired_paid_subscription,
    resolve_account_subscription_for_account,
)
from .models import AccountSubscription

DEFAULT_PLAN = 'free'


def current_account_subscription(account_id: int) -> AccountSubscription | None:
    """Pending or active row; applies scheduled downgrades when prepaid period ended."""
    row, _expired = resolve_account_subscription_for_account(account_id)
    return row


def active_account_subscription(account_id: int) -> AccountSubscription | None:
    """Active prepaid row only (excludes pending/cancelled/expired)."""
    if not account_id:
        return None
    today = timezone.localdate()
    return (
        AccountSubscription.objects.filter(
            account_id=account_id,
            status=AccountSubscription.Status.ACTIVE,
            deleted_at__isnull=True,
        )
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
        .select_related('subscription', 'scheduled_subscription')
        .order_by('-start_date', '-id')
        .first()
    )


def active_subscription_plan_for_account(account_id: int) -> str:
    row = active_account_subscription(account_id)
    if row is None:
        return DEFAULT_PLAN
    return row.subscription.plan


def current_subscription_plan_for_account(account_id: int) -> str:
    """Plan slug from account_subscriptions → subscriptions (pending or active row)."""
    row = current_account_subscription(account_id)
    if row is None:
        return DEFAULT_PLAN
    return row.subscription.plan


def active_paid_account_subscription(account_id: int) -> AccountSubscription | None:
    """Active non-free subscription with a payment reference and a current prepaid period."""
    row = get_account_subscription_row(account_id)
    if row is None:
        return None
    if row.subscription.plan == 'free':
        return None
    if row.status != AccountSubscription.Status.ACTIVE:
        return None
    if is_expired_paid_subscription(row):
        return None
    if not (row.reference_id or '').strip():
        return None
    return row
