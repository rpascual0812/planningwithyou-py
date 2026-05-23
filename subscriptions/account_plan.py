"""Resolve the active subscription plan slug for an account."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .models import AccountSubscription

DEFAULT_PLAN = 'free'


def active_subscription_plan_for_account(account_id: int) -> str:
    """Return ``subscriptions.plan`` for the account's current subscription, else ``free``."""
    today = timezone.localdate()
    row = (
        AccountSubscription.objects.filter(
            account_id=account_id,
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
