"""Apply PayMongo subscription webhook events to account subscriptions."""

from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from bookings.paymongo_webhook import _amount_php_from_paymongo_attributes

from .lifecycle import (
    activate_paid_subscription,
    apply_scheduled_changes_if_due,
    extend_prepaid_period,
)
from .models import AccountSubscription, SubscriptionPayment
from .payment_provider import PROVIDER_LABELS, PROVIDER_PAYMONGO
from .subscription_billing_notifications import (
    invoice_indicates_failed_payment,
    invoice_indicates_successful_payment,
    issue_subscription_payment_receipt,
    notify_subscription_payment_failed,
)

_SUBSCRIPTION_EVENT_PREFIX = 'subscription.'


def _parse_billing_date(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip()[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _subscription_resource_from_event(event: dict) -> tuple[str, dict, str, str]:
    """Return (event_type, attrs, paymongo_subscription_id, resource_id)."""
    data = event.get('data')
    if not isinstance(data, dict):
        return '', {}, '', ''
    event_attrs = data.get('attributes')
    if not isinstance(event_attrs, dict):
        return '', {}, '', ''
    event_type = (
        event.get('type') or event_attrs.get('type') or ''
    ).strip()
    resource = event_attrs.get('data')
    if not isinstance(resource, dict):
        return event_type, {}, '', ''

    resource_type = (resource.get('type') or '').strip()
    resource_id = str(resource.get('id') or '').strip()
    resource_attrs = resource.get('attributes')
    if not isinstance(resource_attrs, dict):
        resource_attrs = {}

    if resource_type == 'subscription':
        sub_id = resource_id or str(resource_attrs.get('id') or '').strip()
        return event_type, resource_attrs, sub_id, resource_id

    if resource_type == 'subscription_invoice':
        sub_id = str(resource_attrs.get('subscription_id') or '').strip()
        return event_type, resource_attrs, sub_id, resource_id

    return event_type, {}, '', ''


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
    del next_billing_date
    apply_scheduled_changes_if_due(account_sub)
    account_sub.refresh_from_db()
    activate_paid_subscription(account_sub)


@transaction.atomic
def _record_recurring_payment(
    account_sub: AccountSubscription,
    *,
    attrs: dict,
    invoice_id: str,
    next_billing_date=None,
) -> SubscriptionPayment | None:
    if invoice_id:
        existing = SubscriptionPayment.objects.filter(
            paymongo_invoice_id=invoice_id,
        ).first()
        if existing is not None:
            issue_subscription_payment_receipt(existing.pk)
            return existing

    amount = _amount_php_from_paymongo_attributes(attrs, 'amount')
    if amount is None:
        amount = account_sub.total_price

    today = timezone.localdate()
    period_start = account_sub.end_date or today
    period_end = next_billing_date
    if period_end is None and account_sub.subscription.plan != 'free':
        from .lifecycle import prepaid_period_end

        period_end = prepaid_period_end(account_sub.subscription, period_start)

    plan_name = account_sub.subscription.name
    payment = SubscriptionPayment.objects.create(
        account_id=account_sub.account_id,
        account_subscription=account_sub,
        amount=amount,
        paid_at=timezone.now(),
        paymongo_invoice_id=invoice_id or '',
        period_start=period_start,
        period_end=period_end,
        description=f'{plan_name} subscription renewal',
    )
    extend_prepaid_period(account_sub, paid_through=period_end)
    issue_subscription_payment_receipt(payment.pk)
    return payment


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
    event_type, attrs, paymongo_sub_id, resource_id = _subscription_resource_from_event(
        event,
    )
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
        if not invoice_indicates_successful_payment(attrs, event_type=event_type):
            return False
        _activate_account_subscription(account_sub, next_billing_date=next_billing)
        _record_recurring_payment(
            account_sub,
            attrs=attrs,
            invoice_id=resource_id,
            next_billing_date=next_billing,
        )
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

    if invoice_indicates_failed_payment(event_type):
        if account_sub.status == AccountSubscription.Status.ACTIVE:
            _mark_subscription_past_due(account_sub)
        failed_amount = _amount_php_from_paymongo_attributes(attrs, 'amount')
        notify_subscription_payment_failed(
            account_sub,
            invoice_id=resource_id,
            amount=failed_amount,
            provider_label=PROVIDER_LABELS[PROVIDER_PAYMONGO],
        )
        return True

    return False
