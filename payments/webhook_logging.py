"""Persist inbound webhook payloads before business logic runs."""

from __future__ import annotations

import json

from .models import WebhookLog

PAYMONGO_WEBHOOK_SOURCE = 'paymongo'


def payload_from_raw_body(raw: bytes):
    """Decode JSON body for storage; fall back to a wrapper if not valid JSON."""
    try:
        return json.loads(raw.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {'_raw': raw.decode('utf-8', errors='replace')}


def log_webhook(source: str, raw: bytes) -> WebhookLog:
    return WebhookLog.objects.create(
        source=source,
        payload=payload_from_raw_body(raw),
    )
