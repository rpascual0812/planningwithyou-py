"""PayMongo Subscriptions API helpers (platform account)."""

from __future__ import annotations

from typing import Any

from bookings.paymongo_client import PayMongoError, _request
from bookings.payment_pricing import amount_to_centavos

from .models import Subscription


def _resource_data(response: dict, label: str) -> dict:
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError(f'Unexpected PayMongo {label} response.')
    return data


def create_customer(
    *,
    email: str,
    first_name: str,
    last_name: str,
    phone: str = '',
    metadata: dict[str, str] | None = None,
) -> dict:
    attributes: dict[str, Any] = {
        'email': email.strip(),
        'first_name': (first_name or 'Account').strip() or 'Account',
        'last_name': (last_name or 'User').strip() or 'User',
        'default_device': 'email',
    }
    phone_digits = ''.join(ch for ch in phone if ch.isdigit() or ch == '+')
    if phone_digits:
        attributes['phone'] = phone_digits
    if metadata:
        attributes['metadata'] = metadata
    response = _request(
        'POST',
        '/customers',
        {'data': {'attributes': attributes}},
    )
    return _resource_data(response, 'customer')


def create_subscription_plan(
    *,
    name: str,
    description: str,
    amount_php: Any,
    billing_cycle: str,
    metadata: dict[str, str] | None = None,
) -> dict:
    amount = amount_to_centavos(amount_php)
    if amount < 2000:
        raise PayMongoError('Subscription amount must be at least PHP 20.00.')
    interval = 'monthly' if billing_cycle == Subscription.BillingCycle.MONTHLY else 'yearly'
    attributes: dict[str, Any] = {
        'name': name[:255],
        'description': description[:255],
        'amount': amount,
        'currency': 'PHP',
        'interval': interval,
        'interval_count': 1,
        'plan_type': 'scheduled',
    }
    if metadata:
        attributes['metadata'] = metadata
    response = _request(
        'POST',
        '/subscriptions/plans',
        {'data': {'attributes': attributes}},
    )
    return _resource_data(response, 'plan')


def create_subscription(*, customer_id: str, plan_id: str) -> dict:
    response = _request(
        'POST',
        '/subscriptions',
        {
            'data': {
                'attributes': {
                    'customer_id': customer_id,
                    'plan_id': plan_id,
                },
            },
        },
    )
    return _resource_data(response, 'subscription')


def retrieve_subscription(subscription_id: str) -> dict:
    response = _request('GET', f'/subscriptions/{subscription_id}')
    return _resource_data(response, 'subscription')


def subscription_checkout_url(subscription: dict) -> str | None:
    """Return PayMongo-hosted URL for the customer to authorize the first payment."""
    attrs = subscription.get('attributes')
    if not isinstance(attrs, dict):
        return None
    setup = attrs.get('setup_intent')
    if isinstance(setup, dict):
        url = (setup.get('next_action_url') or '').strip()
        if url:
            return url
    latest_invoice = attrs.get('latest_invoice')
    if isinstance(latest_invoice, dict):
        payment_intent = latest_invoice.get('payment_intent')
        if isinstance(payment_intent, dict):
            url = (payment_intent.get('next_action_url') or '').strip()
            if url:
                return url
    return None
