"""Handle Xendit webhooks for subscriptions and quotation payment links."""

from __future__ import annotations

import logging

from django.conf import settings

from .xendit_activation import (
    apply_xendit_payment_session_completed,
    apply_xendit_payment_session_failed,
)
from .xendit_recurring import handle_xendit_recurring_webhook_event

logger = logging.getLogger(__name__)

_PAYMENT_SESSION_COMPLETED = 'payment_session.completed'
_PAYMENT_SESSION_EXPIRED = 'payment_session.expired'


def verify_xendit_callback_token(header_value: str | None) -> bool:
    expected = getattr(settings, 'XENDIT_WEBHOOK_TOKEN', '').strip()
    if not expected:
        logger.warning('Xendit webhook rejected: XENDIT_WEBHOOK_TOKEN is not configured.')
        return False
    return (header_value or '').strip() == expected


def _session_data(body: dict) -> dict | None:
    data = body.get('data')
    return data if isinstance(data, dict) else None


def _webhook_data(body: dict) -> dict | None:
    data = _session_data(body)
    if data is not None:
        return data
    raw = body.get('data')
    return raw if isinstance(raw, dict) else None


def handle_xendit_subscription_webhook_body(body: dict) -> bool:
    """Subscription checkout and recurring plan/cycle webhooks."""
    if not isinstance(body, dict):
        return False

    event_type = str(body.get('event') or '').strip()
    data = _webhook_data(body)
    if data is None:
        return False

    if handle_xendit_recurring_webhook_event(event_type, data):
        return True

    if event_type == _PAYMENT_SESSION_COMPLETED:
        return apply_xendit_payment_session_completed(data)
    if event_type == _PAYMENT_SESSION_EXPIRED:
        return apply_xendit_payment_session_failed(data)
    return False


def handle_xendit_payment_link_webhook_body(body: dict) -> bool:
    """Quotation payment link checkout only."""
    if not isinstance(body, dict):
        return False

    from bookings.xendit_booking_webhook import (
        apply_xendit_booking_payment_session_completed,
        apply_xendit_booking_payment_session_failed,
    )

    event_type = str(body.get('event') or '').strip()
    data = _session_data(body)
    if data is None:
        return False

    if event_type == _PAYMENT_SESSION_COMPLETED:
        return apply_xendit_booking_payment_session_completed(data)
    if event_type == _PAYMENT_SESSION_EXPIRED:
        return apply_xendit_booking_payment_session_failed(data)
    return False


def handle_xendit_webhook_body(body: dict) -> bool:
    """Combined handler: recurring/subscription events, then payment links."""
    if not isinstance(body, dict):
        return False

    event_type = str(body.get('event') or '').strip()
    data = _webhook_data(body)
    if data is None:
        return False

    if handle_xendit_recurring_webhook_event(event_type, data):
        return True

    if event_type == _PAYMENT_SESSION_COMPLETED:
        if handle_xendit_payment_link_webhook_body(body):
            return True
        return handle_xendit_subscription_webhook_body(body)

    if event_type == _PAYMENT_SESSION_EXPIRED:
        if handle_xendit_payment_link_webhook_body(body):
            return True
        return handle_xendit_subscription_webhook_body(body)

    return handle_xendit_subscription_webhook_body(body)
