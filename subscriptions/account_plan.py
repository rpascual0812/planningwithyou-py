"""Resolve subscription plan slugs from the single account_subscriptions row."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .lifecycle import current_account_subscription as _current_with_scheduled
from .models import AccountSubscription

DEFAULT_PLAN = 'free'


def current_account_subscription(account_id: int) -> AccountSubscription | None:
    """Pending or active row; applies scheduled downgrades when prepaid period ended."""
    return _current_with_scheduled(account_id)


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
    """Active non-free subscription with PayMongo reference and valid prepaid period."""
    row = active_account_subscription(account_id)
    if row is None:
        return None
    if row.subscription.plan == 'free':
        return None
    if not (row.reference_id or '').strip():
        return None
    return row
