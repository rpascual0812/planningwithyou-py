"""Handle Xendit webhooks for platform subscription billing."""

from __future__ import annotations

import logging

from django.conf import settings

from .xendit_activation import (
    apply_xendit_payment_session_completed,
    apply_xendit_payment_session_failed,
)

logger = logging.getLogger(__name__)

_PAYMENT_SESSION_COMPLETED = 'payment_session.completed'
_PAYMENT_SESSION_EXPIRED = 'payment_session.expired'


def verify_xendit_callback_token(header_value: str | None) -> bool:
    expected = getattr(settings, 'XENDIT_WEBHOOK_TOKEN', '').strip()
    if not expected:
        logger.warning('Xendit webhook rejected: XENDIT_WEBHOOK_TOKEN is not configured.')
        return False
    return (header_value or '').strip() == expected


def handle_xendit_webhook_body(body: dict) -> bool:
    if not isinstance(body, dict):
        return False

    event_type = str(body.get('event') or '').strip()
    data = body.get('data')
    if not isinstance(data, dict):
        return False

    if event_type == _PAYMENT_SESSION_COMPLETED:
        return apply_xendit_payment_session_completed(data)

    if event_type == _PAYMENT_SESSION_EXPIRED:
        return apply_xendit_payment_session_failed(data)

    return False
