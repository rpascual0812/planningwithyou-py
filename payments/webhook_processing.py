"""Run PayMongo webhook handlers after the payload is stored in ``webhook_logs``."""

from __future__ import annotations

import logging

from bookings.paymongo_webhook import (
    handle_paymongo_webhook_event,
    normalize_paymongo_webhook_body,
)
from payments.paymongo_merchant_webhook import handle_paymongo_merchant_webhook_event
from subscriptions.paymongo_webhook_processor import (
    process_subscription_paymongo_webhooks,
)

logger = logging.getLogger(__name__)


def process_paymongo_webhook_body(body: dict) -> bool:
    """
    Process a verified PayMongo webhook JSON body.

    Subscription events are handled first (checkout seat upgrades, recurring
    subscription lifecycle, invoices). Booking and merchant handlers run on
    the normalized event list afterward.
    """
    handled = process_subscription_paymongo_webhooks(body)

    for event in normalize_paymongo_webhook_body(body):
        event_type = (event.get('type') or '').strip()
        if event_type.startswith('subscription.'):
            continue
        try:
            if handle_paymongo_merchant_webhook_event(event):
                handled = True
            elif handle_paymongo_webhook_event(event):
                handled = True
        except Exception:
            logger.exception(
                'PayMongo webhook handler failed for event type=%s',
                event_type or '(unknown)',
            )
            raise

    return handled
