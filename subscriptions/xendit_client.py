"""Minimal Xendit REST client for platform subscription billing."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings

XENDIT_API_BASE = 'https://api.xendit.co'


class XenditError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def xendit_configured() -> bool:
    return bool(getattr(settings, 'XENDIT_SECRET_KEY', '').strip())


def _secret_key() -> str:
    key = getattr(settings, 'XENDIT_SECRET_KEY', '').strip()
    if not key:
        raise XenditError('Xendit is not configured (XENDIT_SECRET_KEY).')
    return key


def _request(method: str, path: str, body: dict | None = None, *, for_user_id: str | None = None) -> dict:
    key = _secret_key()
    url = f'{XENDIT_API_BASE}{path}'
    data = None
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{key}:".encode()).decode()}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    scoped_user = (for_user_id or '').strip()
    if scoped_user:
        headers['for-user-id'] = scoped_user
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
        raise XenditError(message, status_code=exc.code, payload=payload) from exc
    except urllib.error.URLError as exc:
        raise XenditError(f'Xendit network error: {exc.reason}') from exc


def payment_link_url(session: dict) -> str:
    return str(session.get('payment_link_url') or '').strip()


def xendit_session_id(session: dict) -> str:
    """Resolve a payment session id from API or webhook payloads."""
    if not isinstance(session, dict):
        return ''
    for key in ('payment_session_id', 'id'):
        value = str(session.get(key) or '').strip()
        if value:
            return value
    return ''


def retrieve_session(session_id: str, *, for_user_id: str | None = None) -> dict:
    session_id = (session_id or '').strip()
    if not session_id:
        raise XenditError('Xendit session id is required.')
    return _request('GET', f'/sessions/{session_id}', for_user_id=for_user_id)
