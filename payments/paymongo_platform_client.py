"""PayMongo Platforms API (parent secret key, v2 accounts)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings

from bookings.paymongo_client import PayMongoError, _request as _v1_request

from .paymongo_config import paymongo_merchant_children_api_path

PAYMONGO_API_ROOT = 'https://api.paymongo.com'


def _platform_secret() -> str:
    key = (getattr(settings, 'PAYMONGO_SECRET_KEY', None) or '').strip()
    if not key:
        raise PayMongoError('PayMongo is not configured (PAYMONGO_SECRET_KEY).')
    return key


def _platform_request(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    extra_headers: dict[str, str] | None = None,
) -> dict:
    import base64

    url = f'{PAYMONGO_API_ROOT}{path}'
    data = None
    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{_platform_secret()}:".encode()).decode()}',
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
        detail = _errors_detail(payload) or f'PayMongo API error ({exc.code}).'
        raise PayMongoError(
            detail,
            status_code=exc.code,
            payload=payload,
        ) from exc


def _errors_detail(payload: dict | None) -> str:
    if not isinstance(payload, dict):
        return ''
    errors = payload.get('errors')
    if not isinstance(errors, list):
        return ''
    parts: list[str] = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        piece = (item.get('detail') or item.get('title') or '').strip()
        if piece:
            parts.append(piece)
    return ' '.join(parts)


def _resource_id(data: dict) -> str:
    return str(data.get('id') or '').strip()


def _resource_attributes(data: dict) -> dict:
    attrs = data.get('attributes')
    return attrs if isinstance(attrs, dict) else {}


def extract_hosted_url(resource: dict | None) -> str:
    """Pull a redirect URL from PayMongo v1/v2 resource shapes."""
    if not isinstance(resource, dict):
        return ''
    attrs = _resource_attributes(resource)
    for container in (attrs, resource):
        if not isinstance(container, dict):
            continue
        for key in ('checkout_url', 'onboarding_url', 'url', 'verification_url'):
            value = str(container.get(key) or '').strip()
            if value.startswith('http'):
                return value
        redirect = container.get('redirect')
        if isinstance(redirect, dict):
            for key in ('checkout_url', 'url', 'onboarding_url'):
                value = str(redirect.get(key) or '').strip()
                if value.startswith('http'):
                    return value
    return ''


def account_onboarding_url(account: dict) -> str:
    """Onboarding URL on a v2 child account / merchant resource, when present."""
    return extract_hosted_url(account)


def _v1_post_with_fallback(paths: list[str], body: dict) -> dict:
    """Try multiple v1 paths (platform vs legacy) until one succeeds."""
    last_error: PayMongoError | None = None
    for path in paths:
        try:
            return _v1_request('POST', path, body)
        except PayMongoError as exc:
            last_error = exc
            if exc.status_code not in {404, 405}:
                raise
    if last_error is not None:
        raise last_error
    raise PayMongoError('PayMongo merchant API path not found.')


def create_child_merchant(
    *,
    trade_name: str,
    business_type: str,
    email: str,
    phone_number: str,
    features: list[str] | None = None,
) -> dict:
    """
    POST /v1/merchants/children — create a child merchant under the platform.

    See ``PAYMONGO_MERCHANT_CHILDREN_URL``. Returns the PayMongo ``data`` object.
    """
    business: dict[str, str] = {
        'trade_name': trade_name,
        'type': business_type,
        'email': email,
        'phone_number': phone_number,
    }
    response = _platform_request(
        'POST',
        paymongo_merchant_children_api_path(),
        {
            'data': {
                'attributes': {
                    'accepted_terms_and_conditions': True,
                    'features': features if features is not None else ['payment_gateway'],
                    'business': business,
                },
            },
        },
    )
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo create child merchant response.')
    return data


def create_platform_merchant(
    *,
    business_name: str,
    business_type: str,
    email: str,
    mobile_number: str,
) -> dict:
    """Backward-compatible alias for :func:`create_child_merchant`."""
    return create_child_merchant(
        trade_name=business_name,
        business_type=business_type,
        email=email,
        phone_number=mobile_number,
    )


def create_merchant_onboarding_link(merchant_id: str) -> str:
    """
    POST /v1/merchants/{id}/onboarding_links — hosted KYB / document upload.

    Returns the checkout / onboarding URL to redirect the merchant.
    """
    response = _v1_post_with_fallback(
        [
            f'/platform/merchants/{merchant_id}/onboarding_links',
            f'/merchants/{merchant_id}/onboarding_links',
        ],
        {'data': {'attributes': {}}},
    )
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo onboarding link response.')
    url = extract_hosted_url(data)
    if url:
        return url
    raise PayMongoError(
        'PayMongo onboarding link response did not include a redirect URL.',
    )


def _v1_request(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    extra_headers: dict[str, str] | None = None,
) -> dict:
    """PayMongo v1 JSON:API (platform merchants / onboarding links)."""
    return _platform_request(
        method,
        f'/v1{path}',
        body,
        extra_headers=extra_headers,
    )


def create_child_merchant_account() -> dict:
    """POST /v2/accounts — provision a merchant child under the platform."""
    response = _platform_request(
        'POST',
        '/v2/accounts',
        {'type': 'merchant'},
    )
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo create account response.')
    return data


def get_child_account(account_id: str) -> dict:
    response = _platform_request('GET', f'/v2/accounts/{account_id}')
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo account response.')
    return data


def create_identity_verification_session(account_id: str) -> dict:
    """Hosted KYC microsite for the child account representative."""
    response = _platform_request(
        'POST',
        f'/v2/accounts/{account_id}/identity_verification',
        None,
    )
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo identity verification response.')
    return data


def verification_session_url(session: dict) -> str:
    """Extract hosted verification URL from a verification session resource."""
    return extract_hosted_url(session)


def activate_child_account(account_id: str) -> dict:
    response = _platform_request('POST', f'/v2/accounts/{account_id}/activate', {})
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo activate account response.')
    return data


def build_transfer_config(
    *,
    child_account_id: str,
    platform_merchant_id: str,
    platform_fee_bps: int,
) -> dict[str, Any]:
    """
    Split: platform receives ``platform_fee_bps`` basis points of net (1% = 100 bps).
    Remainder stays with the child merchant wallet.
    """
    return {
        'transfer_to': child_account_id,
        'recipients': [
            {
                'merchant_id': platform_merchant_id,
                'split_type': 'percentage_net',
                'value': max(0, int(platform_fee_bps)),
            },
        ],
    }


def create_checkout_session_for_company(
    *,
    child_account_id: str,
    platform_merchant_id: str,
    platform_fee_bps: int,
    line_items: list[dict],
    success_url: str,
    cancel_url: str,
    description: str,
    reference_number: str,
    metadata: dict[str, str],
    send_email_receipt: bool = False,
) -> dict:
    """
    Create checkout on behalf of a linked child with platform fee split.

    Uses parent secret key and optional account-scope header (see settings).
    """
    transfer_config = build_transfer_config(
        child_account_id=child_account_id,
        platform_merchant_id=platform_merchant_id,
        platform_fee_bps=platform_fee_bps,
    )
    scope_header = (
        getattr(settings, 'PAYMONGO_CHILD_ACCOUNT_HEADER', None) or 'Paymongo-Account-Id'
    ).strip()
    extra_headers = {scope_header: child_account_id} if scope_header else None

    attributes: dict[str, Any] = {
        'line_items': line_items,
        'payment_method_types': [
            'card',
            'gcash',
            'grab_pay',
            'paymaya',
            'shopee_pay',
            'qrph',
        ],
        'success_url': success_url,
        'cancel_url': cancel_url,
        'description': description,
        'reference_number': reference_number,
        'metadata': metadata,
        'send_email_receipt': send_email_receipt,
        'show_description': True,
        'show_line_items': True,
        'transfer_config': transfer_config,
    }
    payload = {'data': {'attributes': attributes}}
    response = _v1_request(
        'POST',
        '/checkout_sessions',
        payload,
        extra_headers=extra_headers,
    )
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError('Unexpected PayMongo checkout response.')
    return data
