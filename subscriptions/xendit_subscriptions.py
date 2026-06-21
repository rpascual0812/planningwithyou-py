"""Xendit Payment Sessions for platform subscription billing."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from users.models import User

from .models import Subscription
from .proration import add_months, add_years
from .xendit_client import XenditError, _request, payment_link_url


def _amount_number(amount: Decimal) -> float:
    """Xendit Payment Sessions expect amount as a JSON number (PHP major units)."""
    if amount <= 0:
        raise XenditError('Amount must be greater than zero.')
    return float(amount.quantize(Decimal('0.01')))


def _schedule_for_billing_cycle(billing_cycle: str) -> dict[str, Any]:
    if billing_cycle == Subscription.BillingCycle.YEARLY:
        return {'interval': 'MONTH', 'interval_count': 12}
    return {'interval': 'MONTH', 'interval_count': 1}


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        '+00:00',
        'Z',
    )


def _session_expires_at(*, hours: int = 24) -> datetime:
    """Payment link expiry; Xendit requires at least 10 minutes in the future."""
    return datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=hours)


def _subscription_anchor_date(*, billing_cycle: str, expires_at: datetime) -> datetime:
    """
    First recurring cycle anchor. Xendit requires anchor_date >= session expires_at.
    The initial charge is collected when the session completes; anchor_date schedules renewals.
    """
    if billing_cycle == Subscription.BillingCycle.YEARLY:
        anchor_day = add_years(expires_at.date(), 1)
    else:
        anchor_day = add_months(expires_at.date(), 1)
    anchor = datetime(
        anchor_day.year,
        anchor_day.month,
        min(anchor_day.day, 28),
        tzinfo=timezone.utc,
    )
    if anchor < expires_at:
        anchor = expires_at + timedelta(minutes=1)
    return anchor


def _subscription_schedule(billing_cycle: str) -> tuple[str, dict[str, Any]]:
    expires_at = _session_expires_at()
    anchor = _subscription_anchor_date(
        billing_cycle=billing_cycle,
        expires_at=expires_at,
    )
    schedule = _schedule_for_billing_cycle(billing_cycle)
    schedule.update(
        {
            'anchor_date': _iso_z(anchor),
            'retry_interval': 'DAY',
            'retry_interval_count': 1,
            'total_retry': 3,
            'failed_attempt_notifications': [1, 2, 3],
        },
    )
    return _iso_z(expires_at), schedule


def _customer_payload(
    *,
    account_id: int,
    user: User,
    customer_reference_id: str | None = None,
) -> dict[str, Any]:
    email = (user.email or '').strip()
    given_names = (user.first_name or '').strip() or 'Customer'
    surname = (user.last_name or '').strip() or 'Account'
    reference_id = (customer_reference_id or '').strip()
    if not reference_id:
        reference_id = f'pwu-account-{account_id}-{uuid.uuid4().hex}'
    payload: dict[str, Any] = {
        'reference_id': reference_id[:255],
        'type': 'INDIVIDUAL',
        'email': email or f'account-{account_id}@planningwithyou.local',
        'individual_detail': {
            'given_names': given_names,
            'surname': surname,
        },
    }
    return payload


def _customer_reference_for_session(session_reference_id: str) -> str:
    """Xendit requires a unique customer reference_id for each payment session."""
    base = (session_reference_id or '').strip() or f'pwu-{uuid.uuid4().hex}'
    suffix = '-customer'
    max_base = 255 - len(suffix)
    return f'{base[:max_base]}{suffix}'


def create_subscription_checkout_session(
    *,
    account_id: int,
    user: User,
    reference_id: str,
    description: str,
    amount_php: Decimal,
    billing_cycle: str,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str],
) -> dict:
    expires_at, schedule = _subscription_schedule(billing_cycle)
    body = {
        'reference_id': reference_id[:255],
        'session_type': 'SUBSCRIPTION',
        'mode': 'PAYMENT_LINK',
        'amount': _amount_number(amount_php),
        'currency': 'PHP',
        'country': 'PH',
        'expires_at': expires_at,
        'customer': _customer_payload(
            account_id=account_id,
            user=user,
            customer_reference_id=_customer_reference_for_session(reference_id),
        ),
        'locale': 'en',
        'description': description[:255],
        'subscription': {
            'schedule': schedule,
            'failed_cycle_action': 'RESUME',
        },
        'success_return_url': success_url,
        'cancel_return_url': cancel_url,
        'metadata': metadata,
    }
    session = _request('POST', '/sessions', body)
    url = payment_link_url(session)
    if not url:
        raise XenditError('Xendit did not return a checkout URL for the subscription session.')
    return session


def create_one_time_checkout_session(
    *,
    account_id: int,
    user: User,
    reference_id: str,
    description: str,
    amount_php: Decimal,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str],
) -> dict:
    body = {
        'reference_id': reference_id[:255],
        'session_type': 'PAY',
        'mode': 'PAYMENT_LINK',
        'amount': _amount_number(amount_php),
        'currency': 'PHP',
        'country': 'PH',
        'customer': _customer_payload(
            account_id=account_id,
            user=user,
            customer_reference_id=_customer_reference_for_session(reference_id),
        ),
        'locale': 'en',
        'description': description[:255],
        'success_return_url': success_url,
        'cancel_return_url': cancel_url,
        'metadata': metadata,
    }
    session = _request('POST', '/sessions', body)
    url = payment_link_url(session)
    if not url:
        raise XenditError('Xendit did not return a checkout URL for the payment session.')
    return session
