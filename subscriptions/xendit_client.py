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


def format_xendit_error_message(
    payload: Any,
    *,
    fallback: str = 'Xendit request failed.',
    status_code: int | None = None,
) -> str:
    if not isinstance(payload, dict):
        return fallback

    message = str(payload.get('message') or payload.get('error_code') or fallback)
    errors = payload.get('errors')
    details: list[str] = []
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, dict):
                path = str(item.get('path') or '').strip()
                item_message = str(item.get('message') or '').strip()
                if path and item_message:
                    details.append(f'{path}: {item_message}')
                elif item_message:
                    details.append(item_message)
                elif path:
                    details.append(path)
            else:
                text = str(item).strip()
                if text:
                    details.append(text)
    elif isinstance(errors, dict):
        for key, value in errors.items():
            if isinstance(value, list):
                joined = ', '.join(str(item).strip() for item in value if str(item).strip())
                if joined:
                    details.append(f'{key}: {joined}')
            elif value not in (None, ''):
                details.append(f'{key}: {value}')

    if details:
        message = f'{message} {"; ".join(details)}'

    if status_code == 403:
        message = (
            f'{message} Update the secret key in Xendit Dashboard → Developers → API Keys: '
            'grant Write access for Payment Sessions and Recurring/Subscriptions, '
            'then update XENDIT_SECRET_KEY on the server.'
        )
    elif status_code == 400 and any(
        token in message.lower()
        for token in ('return_url', 'success_return', 'cancel_return')
    ):
        message = (
            f'{message} Xendit requires HTTPS return URLs. Set XENDIT_RETURN_URL_BASE on the '
            'server to your public https:// frontend URL.'
        )

    return message


def xendit_configured() -> bool:
    return bool(getattr(settings, 'XENDIT_SECRET_KEY', '').strip())


def _secret_key() -> str:
    key = getattr(settings, 'XENDIT_SECRET_KEY', '').strip()
    if not key:
        raise XenditError('Xendit is not configured (XENDIT_SECRET_KEY).')
    return key


def _request(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    for_user_id: str | None = None,
    with_split_rule: str | None = None,
) -> dict:
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
    split_rule = (with_split_rule or '').strip()
    if split_rule:
        headers['with-split-rule'] = split_rule
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
        message = format_xendit_error_message(
            payload,
            status_code=exc.code,
        )
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
