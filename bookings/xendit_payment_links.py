"""Xendit Payment Sessions for quotation payment links (xenPlatform sub-accounts)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from subscriptions.xendit_client import XenditError, _request, payment_link_url

from payments.xendit_split_rules import get_platform_fee_split_rule_id


def _amount_number(amount: Decimal) -> float:
    if amount <= 0:
        raise XenditError('Amount must be greater than zero.')
    return float(amount.quantize(Decimal('0.01')))


def _session_expires_at(*, hours: int = 24 * 14) -> str:
    expires = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=hours)
    return expires.isoformat().replace('+00:00', 'Z')


def create_quotation_payment_session(
    *,
    sub_account_id: str,
    reference_id: str,
    description: str,
    amount_php: Decimal,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str],
    customer_email: str,
) -> dict:
    email = (customer_email or '').strip() or 'customer@planningwithyou.local'
    customer_reference = f'pwu-quote-{uuid.uuid4().hex}'[:255]
    body = {
        'reference_id': reference_id[:255],
        'session_type': 'PAY',
        'mode': 'PAYMENT_LINK',
        'amount': _amount_number(amount_php),
        'currency': 'PHP',
        'country': 'PH',
        'expires_at': _session_expires_at(),
        'customer': {
            'reference_id': customer_reference,
            'type': 'INDIVIDUAL',
            'email': email,
            'individual_detail': {
                'given_names': 'Customer',
                'surname': 'Payment',
            },
        },
        'locale': 'en',
        'description': description[:255],
        'success_return_url': success_url,
        'cancel_return_url': cancel_url,
        'metadata': metadata,
    }
    split_rule_id = get_platform_fee_split_rule_id()
    session = _request(
        'POST',
        '/sessions',
        body,
        for_user_id=(sub_account_id or '').strip(),
        with_split_rule=split_rule_id or None,
    )
    url = payment_link_url(session)
    if not url:
        raise XenditError('Xendit did not return a checkout URL for the payment session.')
    return session
