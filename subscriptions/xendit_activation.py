"""Apply Xendit payment session completion to account subscriptions."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from .lifecycle import activate_paid_subscription
from .models import AccountSubscription, Subscription
from .payment_provider import PROVIDER_LABELS, active_subscription_payment_provider
from .proration import apply_subscription_selection
from .subscription_billing_notifications import notify_subscription_payment_failed
from .xendit_billing import _amount_php_from_xendit_session, record_xendit_session_payment
from .xendit_client import XenditError, retrieve_session, xendit_session_id

logger = logging.getLogger(__name__)

_ACTIVATION_KINDS = frozenset({'account_subscription', 'subscription_plan_switch'})
_SEAT_UPGRADE_KIND = 'subscription_seat_upgrade'


def _metadata_from_session(session: dict) -> dict[str, str]:
    metadata = session.get('metadata')
    if not isinstance(metadata, dict):
        return {}
    return {str(k): str(v) for k, v in metadata.items()}


def _session_completed(session: dict) -> bool:
    return str(session.get('status') or '').strip().upper() == 'COMPLETED'


def _needs_activation_after_payment(account_sub: AccountSubscription) -> bool:
    """Skip duplicate webhooks when prepaid access is still current."""
    if account_sub.status != AccountSubscription.Status.ACTIVE:
        return True
    if account_sub.end_date is None:
        return False
    return account_sub.end_date < timezone.localdate()


def _find_account_subscription(
    *,
    metadata: dict[str, str],
    session_id: str,
    checkout_reference_id: str = '',
) -> AccountSubscription | None:
    account_sub_id = (metadata.get('account_subscription_id') or '').strip()
    if account_sub_id.isdigit():
        row = (
            AccountSubscription.objects.select_related('subscription', 'account')
            .filter(pk=int(account_sub_id), deleted_at__isnull=True)
            .first()
        )
        if row is not None:
            return row

    for reference in (session_id, checkout_reference_id):
        ref = (reference or '').strip()
        if not ref:
            continue
        row = (
            AccountSubscription.objects.select_related('subscription', 'account')
            .filter(reference_id=ref, deleted_at__isnull=True)
            .order_by('-id')
            .first()
        )
        if row is not None:
            return row
    return None


def _enrich_session_from_api(session: dict) -> dict:
    """
    Webhook payloads omit session metadata. Fetch the full session when we need
    checkout metadata or a reliable session id.
    """
    session_id = xendit_session_id(session)
    if not session_id:
        return session

    metadata = _metadata_from_session(session)
    if metadata:
        return session

    try:
        full = retrieve_session(session_id)
    except XenditError:
        logger.warning(
            'Xendit session %s could not be retrieved for subscription activation.',
            session_id,
        )
        return session

    if not isinstance(full, dict):
        return session

    merged = dict(full)
    merged.update(session)
    if not xendit_session_id(merged):
        merged['payment_session_id'] = session_id
    return merged


@transaction.atomic
def _apply_seat_upgrade(
    *,
    account_sub: AccountSubscription,
    team_seats: int,
    subscription: Subscription,
) -> None:
    apply_subscription_selection(account_sub, subscription, team_seats)


@transaction.atomic
def apply_xendit_payment_session_completed(session: dict) -> bool:
    """Return True when the session was handled for a subscription checkout."""
    if not _session_completed(session):
        return False

    session = _enrich_session_from_api(session)
    session_id = xendit_session_id(session)
    metadata = _metadata_from_session(session)
    checkout_reference_id = str(session.get('reference_id') or '').strip()
    kind = (metadata.get('kind') or '').strip()

    account_sub = _find_account_subscription(
        metadata=metadata,
        session_id=session_id,
        checkout_reference_id=checkout_reference_id,
    )
    if account_sub is None:
        logger.info(
            'Xendit session %s had no matching account subscription (reference=%s).',
            session_id,
            checkout_reference_id,
        )
        return False

    if session_id and account_sub.reference_id != session_id:
        account_sub.reference_id = session_id
        account_sub.save(update_fields=['reference_id', 'updated_at'])

    subscription_block = session.get('subscription')
    if isinstance(subscription_block, dict):
        plan_id = str(
            subscription_block.get('plan_id')
            or subscription_block.get('recurring_plan_id')
            or '',
        ).strip()
        if plan_id and account_sub.reference_id != plan_id:
            account_sub.reference_id = plan_id
            account_sub.save(update_fields=['reference_id', 'updated_at'])

    if kind == _SEAT_UPGRADE_KIND:
        try:
            team_seats = int(metadata['team_seats'])
            subscription_id = int(metadata['subscription_id'])
        except (KeyError, TypeError, ValueError):
            return False
        subscription = Subscription.objects.filter(pk=subscription_id).first()
        if subscription is None:
            return False
        _apply_seat_upgrade(
            account_sub=account_sub,
            team_seats=team_seats,
            subscription=subscription,
        )
        record_xendit_session_payment(account_sub, session, kind=kind)
        return True

    if kind and kind not in _ACTIVATION_KINDS:
        if str(session.get('session_type') or '').strip().upper() == 'SUBSCRIPTION':
            kind = 'account_subscription'
        else:
            return False

    subscription = account_sub.subscription
    subscription_id = (metadata.get('subscription_id') or '').strip()
    if subscription_id.isdigit():
        selected = Subscription.objects.filter(pk=int(subscription_id)).first()
        if selected is not None:
            subscription = selected

    team_seats = account_sub.team_seats
    raw_seats = (metadata.get('team_seats') or '').strip()
    if raw_seats.isdigit():
        team_seats = int(raw_seats)

    if _needs_activation_after_payment(account_sub):
        activate_paid_subscription(
            account_sub,
            subscription=subscription,
            team_seats=team_seats,
        )

    record_xendit_session_payment(account_sub, session, kind=kind or 'account_subscription')
    return True


_FAILED_SESSION_STATUSES = frozenset({'EXPIRED', 'CANCELED'})


def _session_status(session: dict) -> str:
    return str(session.get('status') or '').strip().upper()


def apply_xendit_payment_session_failed(session: dict) -> bool:
    """Notify the account when a Xendit checkout session expires or is canceled."""
    status = _session_status(session)
    if status not in _FAILED_SESSION_STATUSES:
        return False

    session_id = xendit_session_id(session)
    metadata = _metadata_from_session(session)
    checkout_reference_id = str(session.get('reference_id') or '').strip()

    account_sub = _find_account_subscription(
        metadata=metadata,
        session_id=session_id,
        checkout_reference_id=checkout_reference_id,
    )
    if account_sub is None:
        logger.info(
            'Xendit failed session %s had no matching account subscription (reference=%s).',
            session_id,
            checkout_reference_id,
        )
        return False

    provider = active_subscription_payment_provider()
    provider_label = PROVIDER_LABELS.get(provider, provider.title())
    amount = _amount_php_from_xendit_session(session, account_sub.total_price)
    notice_key = session_id or checkout_reference_id or str(account_sub.pk)

    notify_subscription_payment_failed(
        account_sub,
        invoice_id=f'xendit-{notice_key}-{status.lower()}',
        amount=amount,
        provider_label=provider_label,
    )
    return True
