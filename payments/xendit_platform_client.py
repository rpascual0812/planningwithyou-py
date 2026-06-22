"""Xendit xenPlatform REST helpers for company sub-accounts."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

from .xendit_config import xendit_secret_key


class XenditPlatformError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _request(method: str, path: str, body: dict | None = None) -> dict:
    key = xendit_secret_key()
    if not key:
        raise XenditPlatformError('Xendit is not configured (XENDIT_SECRET_KEY).')
    url = f'https://api.xendit.co{path}'
    data = None
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{key}:".encode()).decode()}',
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
        except Exception:
            payload = None
        message = 'Xendit request failed.'
        if isinstance(payload, dict):
            message = str(payload.get('message') or payload.get('error_code') or message)
        raise XenditPlatformError(message, status_code=exc.code, payload=payload) from exc
    except urllib.error.URLError as exc:
        raise XenditPlatformError(f'Xendit network error: {exc.reason}') from exc


def create_sub_account(
    *,
    email: str,
    business_name: str,
    account_type: str = 'MANAGED',
) -> dict:
    """Create a xenPlatform sub-account (MANAGED for third-party merchant KYB)."""
    normalized_type = (account_type or 'MANAGED').strip().upper()
    if normalized_type not in {'MANAGED', 'OWNED'}:
        raise XenditPlatformError('Invalid Xendit sub-account type.')
    return _request(
        'POST',
        '/v2/accounts',
        {
            'email': email.strip(),
            'type': normalized_type,
            'public_profile': {
                'business_name': business_name.strip(),
            },
        },
    )


def create_managed_sub_account(*, email: str, business_name: str) -> dict:
    return create_sub_account(
        email=email,
        business_name=business_name,
        account_type='MANAGED',
    )


def get_sub_account(account_id: str) -> dict:
    account_id = (account_id or '').strip()
    if not account_id:
        raise XenditPlatformError('Xendit account id is required.')
    return _request('GET', f'/v2/accounts/{account_id}')
