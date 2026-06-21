"""Record subscription payments and receipts from Xendit payment session webhooks."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .lifecycle import PREPAID_PERIOD_DAYS
from .models import AccountSubscription, SubscriptionPayment
from .proration import billing_period_end
from .subscription_billing_notifications import issue_subscription_payment_receipt
from .xendit_client import xendit_session_id

TWOPLACES = Decimal('0.01')


def _amount_php_from_xendit_session(session: dict, fallback: Decimal) -> Decimal:
    raw = session.get('amount')
    if raw is None or raw == '':
        return fallback
    try:
        amount = Decimal(str(raw))
    except InvalidOperation:
        return fallback
    if amount <= 0:
        return fallback
    return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _payment_description(account_sub: AccountSubscription, kind: str) -> str:
    plan_name = account_sub.subscription.name
    if kind == 'subscription_seat_upgrade':
        return f'{plan_name} subscription seat upgrade'
    if kind == 'subscription_plan_switch':
        return f'{plan_name} subscription plan change'
    return f'{plan_name} subscription payment'


def _period_for_payment(
    account_sub: AccountSubscription,
    *,
    kind: str,
) -> tuple[date, date | None]:
    today = timezone.localdate()
    account_sub.refresh_from_db()

    if kind == 'subscription_seat_upgrade':
        return today, billing_period_end(account_sub)

    period_start = account_sub.start_date or today
    period_end = account_sub.end_date
    if period_end is None and account_sub.subscription.plan != 'free':
        period_end = period_start + timedelta(days=PREPAID_PERIOD_DAYS)
    return period_start, period_end


@transaction.atomic
def record_xendit_session_payment(
    account_sub: AccountSubscription,
    session: dict,
    *,
    kind: str = '',
) -> SubscriptionPayment | None:
    """
    Idempotently create ``SubscriptionPayment`` and PDF receipt for a completed
    Xendit payment session. External ids are stored in ``paymongo_*`` columns
    for historical schema compatibility.
    """
    session_id = xendit_session_id(session)
    payment_id = str(session.get('payment_id') or '').strip()

    if payment_id:
        existing = SubscriptionPayment.objects.filter(
            paymongo_payment_id=payment_id,
        ).first()
        if existing is not None:
            issue_subscription_payment_receipt(existing.pk)
            return existing

    if session_id:
        existing = SubscriptionPayment.objects.filter(
            paymongo_invoice_id=session_id,
        ).first()
        if existing is not None:
            issue_subscription_payment_receipt(existing.pk)
            return existing

    if not session_id and not payment_id:
        return None

    amount = _amount_php_from_xendit_session(session, account_sub.total_price)
    period_start, period_end = _period_for_payment(account_sub, kind=kind)

    payment = SubscriptionPayment.objects.create(
        account_id=account_sub.account_id,
        account_subscription=account_sub,
        amount=amount,
        paid_at=timezone.now(),
        paymongo_invoice_id=session_id or '',
        paymongo_payment_id=payment_id or '',
        period_start=period_start,
        period_end=period_end,
        description=_payment_description(account_sub, kind),
    )
    issue_subscription_payment_receipt(payment.pk)
    return payment
