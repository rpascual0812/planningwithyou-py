"""Resolve subscription plan slugs from account_subscriptions → subscriptions."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .models import AccountSubscription

DEFAULT_PLAN = 'free'


def current_account_subscription(account_id: int) -> AccountSubscription | None:
    """Pending or active ``account_subscriptions`` row for the account, with ``subscription``."""
    if not account_id:
        return None
    today = timezone.localdate()
    return (
        AccountSubscription.objects.filter(
            account_id=account_id,
            deleted_at__isnull=True,
        )
        .filter(
            Q(status=AccountSubscription.Status.PENDING)
            | (
                Q(status=AccountSubscription.Status.ACTIVE)
                & (Q(end_date__isnull=True) | Q(end_date__gte=today))
            ),
        )
        .select_related('subscription')
        .order_by('-status', '-start_date', '-id')
        .first()
    )


def current_subscription_plan_for_account(account_id: int) -> str:
    """``subscriptions.plan`` for the account's current row (via ``users.account_id``), else ``free``."""
    row = current_account_subscription(account_id)
    if row is None:
        return DEFAULT_PLAN
    return row.subscription.plan


def active_subscription_plan_for_account(account_id: int) -> str:
    """Return ``subscriptions.plan`` for the account's current subscription, else ``free``."""
    today = timezone.localdate()
    row = (
        AccountSubscription.objects.filter(
            account_id=account_id,
            status=AccountSubscription.Status.ACTIVE,
            deleted_at__isnull=True,
        )
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
        .select_related('subscription')
        .order_by('-start_date', '-id')
        .first()
    )
    if row is None:
        return DEFAULT_PLAN
    return row.subscription.plan
