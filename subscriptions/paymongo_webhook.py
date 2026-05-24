"""Apply PayMongo subscription webhook events to account subscriptions."""

from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from .models import AccountSubscription


_SUBSCRIPTION_EVENT_PREFIX = 'subscription.'


def _parse_billing_date(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip()[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _subscription_resource_from_event(event: dict) -> tuple[str, dict, str]:
    """Return (event_type, subscription_attrs, paymongo_subscription_id)."""
    data = event.get('data')
    if not isinstance(data, dict):
        return '', {}, ''
    event_attrs = data.get('attributes')
    if not isinstance(event_attrs, dict):
        return '', {}, ''
    event_type = (
        event.get('type') or event_attrs.get('type') or ''
    ).strip()
    resource = event_attrs.get('data')
    if not isinstance(resource, dict):
        return event_type, {}, ''

    resource_type = (resource.get('type') or '').strip()
    resource_id = str(resource.get('id') or '').strip()
    resource_attrs = resource.get('attributes')
    if not isinstance(resource_attrs, dict):
        resource_attrs = {}

    if resource_type == 'subscription':
        sub_id = resource_id or str(resource_attrs.get('id') or '').strip()
        return event_type, resource_attrs, sub_id

    if resource_type == 'subscription_invoice':
        sub_id = str(resource_attrs.get('subscription_id') or '').strip()
        return event_type, resource_attrs, sub_id

    return event_type, {}, ''


def _find_account_subscription(paymongo_subscription_id: str) -> AccountSubscription | None:
    if not paymongo_subscription_id:
        return None
    return (
        AccountSubscription.objects.select_related('subscription', 'account')
        .filter(reference_id=paymongo_subscription_id, deleted_at__isnull=True)
        .order_by('-id')
        .first()
    )


@transaction.atomic
def _activate_account_subscription(
    account_sub: AccountSubscription,
    *,
    next_billing_date=None,
) -> None:
    today = timezone.localdate()
    AccountSubscription.objects.filter(
        account_id=account_sub.account_id,
        status=AccountSubscription.Status.ACTIVE,
        deleted_at__isnull=True,
    ).exclude(pk=account_sub.pk).update(
        status=AccountSubscription.Status.CANCELLED,
        end_date=today,
        updated_at=timezone.now(),
    )
    account_sub.status = AccountSubscription.Status.ACTIVE
    account_sub.start_date = today
    account_sub.end_date = next_billing_date
    account_sub.save(
        update_fields=['status', 'start_date', 'end_date', 'updated_at'],
    )


@transaction.atomic
def _cancel_account_subscription(account_sub: AccountSubscription) -> None:
    today = timezone.localdate()
    if account_sub.status == AccountSubscription.Status.PENDING:
        account_sub.status = AccountSubscription.Status.CANCELLED
        account_sub.end_date = today
        account_sub.save(update_fields=['status', 'end_date', 'updated_at'])
        return
    if account_sub.status == AccountSubscription.Status.ACTIVE:
        account_sub.status = AccountSubscription.Status.CANCELLED
        account_sub.end_date = today
        account_sub.save(update_fields=['status', 'end_date', 'updated_at'])


@transaction.atomic
def _mark_subscription_past_due(account_sub: AccountSubscription) -> None:
    if account_sub.status != AccountSubscription.Status.ACTIVE:
        return
    account_sub.status = AccountSubscription.Status.PAST_DUE
    account_sub.save(update_fields=['status', 'updated_at'])


@transaction.atomic
def _mark_subscription_unpaid(account_sub: AccountSubscription) -> None:
    today = timezone.localdate()
    account_sub.status = AccountSubscription.Status.UNPAID
    account_sub.end_date = today
    account_sub.save(update_fields=['status', 'end_date', 'updated_at'])


def handle_paymongo_subscription_webhook_event(event: dict) -> bool:
    event_type, attrs, paymongo_sub_id = _subscription_resource_from_event(event)
    if not event_type.startswith(_SUBSCRIPTION_EVENT_PREFIX):
        return False

    account_sub = _find_account_subscription(paymongo_sub_id)
    if account_sub is None:
        return False

    status = (attrs.get('status') or '').strip().lower()
    next_billing = _parse_billing_date(attrs.get('next_billing_schedule'))

    if event_type == 'subscription.activated' or status == 'active':
        _activate_account_subscription(account_sub, next_billing_date=next_billing)
        return True

    if event_type == 'subscription.invoice.paid':
        _activate_account_subscription(account_sub, next_billing_date=next_billing)
        return True

    if event_type in {'subscription.past_due'} or status == 'past_due':
        _mark_subscription_past_due(account_sub)
        return True

    if event_type in {'subscription.unpaid'} or status == 'unpaid':
        _mark_subscription_unpaid(account_sub)
        return True

    if event_type == 'subscription.updated' and status in {
        'cancelled',
        'incomplete_cancelled',
    }:
        _cancel_account_subscription(account_sub)
        return True

    if event_type == 'subscription.invoice.payment_failed':
        if account_sub.status == AccountSubscription.Status.ACTIVE:
            _mark_subscription_past_due(account_sub)
        return True

    return False
