"""Minimal PayMongo REST client (platform secret key)."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings

PAYMONGO_API_BASE = 'https://api.paymongo.com/v1'

# All standard checkout methods (merchant must have them enabled in PayMongo).
CHECKOUT_PAYMENT_METHOD_TYPES = [
    'card',
    'gcash',
    'grab_pay',
    'paymaya',
    'shopee_pay',
    'qrph',
    'billease',
    'dob',
    'dob_ubp',
    'brankas_bdo',
    'brankas_landbank',
    'brankas_metrobank',
]


class PayMongoError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def paymongo_configured() -> bool:
    return bool((getattr(settings, 'PAYMONGO_SECRET_KEY', None) or '').strip())


def _secret_key() -> str:
    key = (getattr(settings, 'PAYMONGO_SECRET_KEY', None) or '').strip()
    if not key:
        raise PayMongoError('PayMongo is not configured (PAYMONGO_SECRET_KEY).')
    return key


def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = f'{PAYMONGO_API_BASE}{path}'
    data = None
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{_secret_key()}:".encode()).decode()}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if body is not None:
        data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        payload = None
        try:
            payload = json.loads(exc.read().decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None
        detail = ''
        if isinstance(payload, dict):
            errors = payload.get('errors')
            if isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, dict):
                    detail = first.get('detail') or first.get('title') or ''
        raise PayMongoError(
            detail or f'PayMongo API error ({exc.code}).',
            status_code=exc.code,
            payload=payload,
        ) from exc


def create_checkout_session(
    *,
    line_items: list[dict],
    success_url: str,
    cancel_url: str,
    description: str,
    reference_number: str,
    metadata: dict[str, str],
    send_email_receipt: bool = False,
) -> dict:
    """Create a hosted checkout session; returns PayMongo ``data`` object."""
    attributes: dict[str, Any] = {
        'line_items': line_items,
        'payment_method_types': CHECKOUT_PAYMENT_METHOD_TYPES,
        'success_url': success_url,
        'cancel_url': cancel_url,
        'description': description,
        'reference_number': reference_number,
        'metadata': metadata,
        'send_email_receipt': send_email_receipt,
        'show_description': True,
        'show_line_items': True,
    }
    payload = {'data': {'attributes': attributes}}
    response = _request('POST', '/checkout_sessions', payload)
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo checkout response.')
    return data


def retrieve_checkout_session(session_id: str) -> dict:
    response = _request('GET', f'/checkout_sessions/{session_id}')
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo checkout response.')
    return data
