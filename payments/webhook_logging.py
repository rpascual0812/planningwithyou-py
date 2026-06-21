"""Persist inbound webhook payloads before business logic runs."""

from __future__ import annotations

import json

from django.utils import timezone

from .models import WebhookLog

PAYMONGO_WEBHOOK_SOURCE = 'paymongo'


def payload_from_raw_body(raw: bytes):
    """Decode JSON body for storage; fall back to a wrapper if not valid JSON."""
    try:
        return json.loads(raw.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {'_raw': raw.decode('utf-8', errors='replace')}


def log_webhook(source: str, raw: bytes, *, meta: dict | None = None) -> WebhookLog:
    """Store an inbound webhook payload before signature checks or handlers run."""
    payload = payload_from_raw_body(raw)
    if meta:
        if isinstance(payload, dict):
            payload = {**payload, '_request_meta': meta}
        else:
            payload = {'_payload': payload, '_request_meta': meta}
    return WebhookLog.objects.create(
        source=source,
        payload=payload,
    )


def finalize_webhook_log(
    log: WebhookLog,
    *,
    handled: bool,
    error_message: str = '',
) -> WebhookLog:
    log.processed_at = timezone.now()
    log.handled = handled
    log.error_message = (error_message or '')[:4000]
    log.save(update_fields=['processed_at', 'handled', 'error_message'])
    return log
