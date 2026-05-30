"""Process subscription-related PayMongo webhook payloads (after webhook_logs insert)."""

from __future__ import annotations

import logging

from bookings.paymongo_webhook import normalize_paymongo_webhook_body

from .paymongo_checkout_webhook import handle_subscription_checkout_webhook_event
from .paymongo_webhook import handle_paymongo_subscription_webhook_event

logger = logging.getLogger(__name__)

_SUBSCRIPTION_CHECKOUT_EVENT_TYPES = frozenset({
    'checkout.session.completed',
    'payment.paid',
})


def process_subscription_paymongo_webhooks(body: dict) -> bool:
    """
    Apply subscription checkout and recurring subscription handlers for one payload.
    Call only after the request body is stored in ``webhook_logs``.
    """
    handled = False
    for event in normalize_paymongo_webhook_body(body):
        event_type = (event.get('type') or '').strip()
        try:
            if event_type in _SUBSCRIPTION_CHECKOUT_EVENT_TYPES:
                if handle_subscription_checkout_webhook_event(event):
                    handled = True
                continue
            if event_type.startswith('subscription.'):
                if handle_paymongo_subscription_webhook_event(event):
                    handled = True
        except Exception:
            logger.exception(
                'Subscription webhook handler failed for event type=%s',
                event_type or '(unknown)',
            )
            raise
    return handled
