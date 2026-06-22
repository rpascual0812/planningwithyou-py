"""Apply Xendit recurring subscription plan and cycle webhooks."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .lifecycle import extend_prepaid_period, prepaid_period_end
from .models import AccountSubscription, SubscriptionPayment
from .payment_provider import PROVIDER_LABELS, active_subscription_payment_provider
from .subscription_billing_notifications import (
    issue_subscription_payment_receipt,
    notify_subscription_payment_failed,
)

logger = logging.getLogger(__name__)

TWOPLACES = Decimal('0.01')

_RECURRING_PLAN_ACTIVATED_EVENTS = frozenset({
    'recurring.plan.activated',
    'recurring_plan.activated',
})
_RECURRING_CYCLE_SUCCEEDED = 'recurring.cycle.succeeded'
_RECURRING_CYCLE_FAILED = 'recurring.cycle.failed'


def _metadata_dict(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def _amount_from_data(data: dict, account_sub: AccountSubscription) -> Decimal:
    for key in ('amount', 'cycle_amount', 'billed_amount'):
        raw = data.get(key)
        if raw is None or raw == '':
            continue
        try:
            amount = Decimal(str(raw))
        except InvalidOperation:
            continue
        if amount > 0:
            return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return account_sub.total_price


def _find_account_subscription_for_recurring_event(data: dict) -> AccountSubscription | None:
    plan_id = str(data.get('plan_id') or data.get('recurring_plan_id') or '').strip()
    if plan_id:
        row = (
            AccountSubscription.objects.select_related('subscription', 'account')
            .filter(reference_id=plan_id, deleted_at__isnull=True)
            .order_by('-id')
            .first()
        )
        if row is not None:
            return row

    reference_id = str(data.get('reference_id') or '').strip()
    if reference_id:
        row = (
            AccountSubscription.objects.select_related('subscription', 'account')
            .filter(reference_id=reference_id, deleted_at__isnull=True)
            .order_by('-id')
            .first()
        )
        if row is not None:
            return row

    metadata = _metadata_dict(data.get('metadata'))
    account_sub_id = (metadata.get('account_subscription_id') or '').strip()
    if account_sub_id.isdigit():
        return (
            AccountSubscription.objects.select_related('subscription', 'account')
            .filter(pk=int(account_sub_id), deleted_at__isnull=True)
            .first()
        )

    account_sub_uuid = (metadata.get('account_subscription_uuid') or '').strip()
    if account_sub_uuid:
        return (
            AccountSubscription.objects.select_related('subscription', 'account')
            .filter(uuid=account_sub_uuid, deleted_at__isnull=True)
            .first()
        )
    return None


@transaction.atomic
def apply_xendit_recurring_plan_activated(data: dict) -> bool:
    """Persist the Xendit recurring plan id on the account subscription row."""
    if not isinstance(data, dict):
        return False

    account_sub = _find_account_subscription_for_recurring_event(data)
    if account_sub is None:
        logger.info('Xendit recurring plan activation had no matching account subscription.')
        return False

    plan_id = str(
        data.get('plan_id')
        or data.get('recurring_plan_id')
        or data.get('id')
        or '',
    ).strip()
    if plan_id and account_sub.reference_id != plan_id:
        account_sub.reference_id = plan_id
        account_sub.save(update_fields=['reference_id', 'updated_at'])
    return True


@transaction.atomic
def apply_xendit_recurring_cycle_succeeded(data: dict) -> bool:
    """Record a successful Xendit subscription renewal and extend prepaid access."""
    if not isinstance(data, dict):
        return False

    account_sub = _find_account_subscription_for_recurring_event(data)
    if account_sub is None:
        logger.info('Xendit recurring cycle success had no matching account subscription.')
        return False

    action_id = str(
        data.get('action_id')
        or data.get('payment_id')
        or data.get('id')
        or '',
    ).strip()
    cycle_id = str(data.get('cycle_id') or '').strip()
    invoice_id = action_id or cycle_id
    if invoice_id:
        existing = SubscriptionPayment.objects.filter(
            paymongo_payment_id=invoice_id,
        ).first()
        if existing is not None:
            issue_subscription_payment_receipt(existing.pk)
            return True

    amount = _amount_from_data(data, account_sub)
    today = timezone.localdate()
    period_start = account_sub.end_date or today
    period_end = prepaid_period_end(account_sub.subscription, period_start)

    plan_name = account_sub.subscription.name
    payment = SubscriptionPayment.objects.create(
        account_id=account_sub.account_id,
        account_subscription=account_sub,
        amount=amount,
        paid_at=timezone.now(),
        paymongo_invoice_id=cycle_id or invoice_id,
        paymongo_payment_id=invoice_id or '',
        period_start=period_start,
        period_end=period_end,
        description=f'{plan_name} subscription renewal',
    )
    extend_prepaid_period(account_sub, paid_through=period_end)
    issue_subscription_payment_receipt(payment.pk)
    return True


@transaction.atomic
def apply_xendit_recurring_cycle_failed(data: dict) -> bool:
    """Notify the account when a Xendit subscription renewal cycle fails."""
    if not isinstance(data, dict):
        return False

    account_sub = _find_account_subscription_for_recurring_event(data)
    if account_sub is None:
        return False

    provider = active_subscription_payment_provider()
    provider_label = PROVIDER_LABELS.get(provider, provider.title())
    amount = _amount_from_data(data, account_sub)
    cycle_id = str(data.get('cycle_id') or data.get('id') or '').strip()
    plan_id = str(data.get('plan_id') or account_sub.reference_id or '').strip()
    notice_key = cycle_id or plan_id or str(account_sub.pk)

    notify_subscription_payment_failed(
        account_sub,
        invoice_id=f'xendit-cycle-{notice_key}-failed',
        amount=amount,
        provider_label=provider_label,
    )
    return True


def handle_xendit_recurring_webhook_event(event_type: str, data: dict | None) -> bool:
    if not isinstance(data, dict):
        return False

    if event_type in _RECURRING_PLAN_ACTIVATED_EVENTS:
        return apply_xendit_recurring_plan_activated(data)
    if event_type == _RECURRING_CYCLE_SUCCEEDED:
        return apply_xendit_recurring_cycle_succeeded(data)
    if event_type == _RECURRING_CYCLE_FAILED:
        return apply_xendit_recurring_cycle_failed(data)
    return False
