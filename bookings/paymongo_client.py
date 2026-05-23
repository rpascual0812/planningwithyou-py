"""Minimal PayMongo REST client (platform parent secret key)."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

from payments.paymongo_config import (
    get_paymongo_company_context,
    paymongo_configured as _paymongo_configured,
    platform_secret_key,
)

PAYMONGO_API_BASE = 'https://api.paymongo.com/v1'

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


def paymongo_configured(company_id: int | None = None) -> bool:
    return _paymongo_configured(company_id)


def _secret_key(company_id: int | None = None) -> str:
    key = platform_secret_key()
    if not key:
        raise PayMongoError('PayMongo is not configured (PAYMONGO_SECRET_KEY).')
    return key


def _request(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    company_id: int | None = None,
    secret_key: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict:
    key = (secret_key or '').strip() or _secret_key(company_id)
    url = f'{PAYMONGO_API_BASE}{path}'
    data = None
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{key}:".encode()).decode()}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if extra_headers:
        headers.update(extra_headers)
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
    company_id: int | None = None,
    secret_key: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict:
    """Create checkout; prefer ``payments.paymongo_platform_client`` for Platforms split."""
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
    response = _request(
        'POST',
        '/checkout_sessions',
        payload,
        company_id=company_id,
        secret_key=secret_key,
        extra_headers=extra_headers,
    )
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo checkout response.')
    return data


def retrieve_checkout_session(
    session_id: str,
    *,
    company_id: int | None = None,
    secret_key: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict:
    response = _request(
        'GET',
        f'/checkout_sessions/{session_id}',
        company_id=company_id,
        secret_key=secret_key,
        extra_headers=extra_headers,
    )
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo checkout response.')
    return data


def retrieve_payment(
    payment_id: str,
    *,
    company_id: int | None = None,
    secret_key: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict:
    response = _request(
        'GET',
        f'/payments/{payment_id}',
        company_id=company_id,
        secret_key=secret_key,
        extra_headers=extra_headers,
    )
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo payment response.')
    return data


def child_account_headers(child_account_id: str | None) -> dict[str, str] | None:
    from django.conf import settings

    child_id = (child_account_id or '').strip()
    if not child_id:
        return None
    header = (
        getattr(settings, 'PAYMONGO_CHILD_ACCOUNT_HEADER', None) or 'Paymongo-Account-Id'
    ).strip()
    if not header:
        return None
    return {header: child_id}
