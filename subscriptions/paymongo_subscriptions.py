"""PayMongo Subscriptions API helpers (platform account)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from bookings.paymongo_client import PayMongoError, _request, create_checkout_session
from bookings.payment_pricing import amount_to_centavos

from .models import AccountSubscription, Subscription
from .pricing import compute_subscription_pricing, plan_users

logger = logging.getLogger(__name__)


def _resource_data(response: dict, label: str) -> dict:
    data = response.get('data')
    if not isinstance(data, dict):
        raise PayMongoError(f'Unexpected PayMongo {label} response.')
    return data


def customer_id_from_resource(customer: dict) -> str:
    return str(customer.get('id') or '').strip()


def find_customers_by_email(email: str) -> list[dict]:
    """Return PayMongo customer resources matching ``email`` (may be empty)."""
    normalized = email.strip()
    if not normalized:
        return []
    response = _request('GET', f'/customers?email={quote(normalized, safe="")}')
    data = response.get('data')
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def duplicate_customer_email_error(exc: PayMongoError) -> bool:
    message = str(exc).lower()
    return 'email already exists' in message or 'customer with this email' in message


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


def cancel_paymongo_subscription(subscription_id: str) -> dict:
    """Cancel a PayMongo recurring subscription immediately."""
    sub_id = (subscription_id or '').strip()
    if not sub_id:
        raise PayMongoError('Subscription id is required.')
    response = _request(
        'POST',
        f'/subscriptions/{sub_id}/cancel',
        {
            'data': {
                'attributes': {
                    'cancellation_reason': 'switched_service',
                },
            },
        },
    )
    return _resource_data(response, 'subscription')


def change_subscription_plan(*, subscription_id: str, plan_id: str) -> dict:
    """Point an existing PayMongo subscription at a new plan (recurring amount)."""
    response = _request(
        'PUT',
        f'/subscriptions/{subscription_id}',
        {
            'data': {
                'attributes': {
                    'plan_id': plan_id,
                },
            },
        },
    )
    return _resource_data(response, 'subscription')


def update_account_subscription_recurring_plan(
    account_sub: AccountSubscription,
    subscription: Subscription,
    team_seats: int,
) -> bool:
    """
    Create a PayMongo plan for the new recurring amount and attach it to the
    existing subscription. Returns False when skipped or PayMongo rejects the call
    (e.g. subscription payment methods not enabled on the org).
    """
    paymongo_sub_id = (account_sub.reference_id or '').strip()
    if not paymongo_sub_id:
        return False
    pricing = compute_subscription_pricing(subscription, team_seats)
    users = plan_users(subscription, pricing.team_seats)
    plan_label = (
        f'{subscription.name} · {users} user{"s" if users != 1 else ""} · '
        f'{subscription.get_billing_cycle_display()}'
    )
    try:
        plan = create_subscription_plan(
            name=plan_label,
            description=f'Planning With You {subscription.plan} subscription',
            amount_php=pricing.total_price,
            billing_cycle=subscription.billing_cycle,
            metadata={
                'kind': 'account_subscription_recurring',
                'account_id': str(account_sub.account_id),
                'account_subscription_uuid': str(account_sub.uuid),
            },
        )
        plan_id = str(plan.get('id') or '').strip()
        if not plan_id:
            logger.warning(
                'PayMongo plan create returned no id for account_subscription=%s',
                account_sub.uuid,
            )
            return False
        change_subscription_plan(subscription_id=paymongo_sub_id, plan_id=plan_id)
    except PayMongoError as exc:
        logger.warning(
            'PayMongo recurring plan update failed for account_subscription=%s: %s',
            account_sub.uuid,
            exc,
        )
        return False
    return True


def create_one_time_checkout(
    *,
    amount_php: Any,
    description: str,
    reference_number: str,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str],
) -> dict:
    """Platform checkout session for a single prorated charge."""
    amount = amount_to_centavos(amount_php)
    if amount < 2000:
        raise PayMongoError('Checkout amount must be at least PHP 20.00.')
    session = create_checkout_session(
        line_items=[
            {
                'currency': 'PHP',
                'amount': amount,
                'name': description[:255],
                'quantity': 1,
            },
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        description=description[:255],
        reference_number=reference_number,
        metadata=metadata,
    )
    return session


def one_time_checkout_url(session: dict) -> str | None:
    attrs = session.get('attributes')
    if not isinstance(attrs, dict):
        return None
    url = (attrs.get('checkout_url') or '').strip()
    if url:
        return url
    redirect = attrs.get('redirect')
    if isinstance(redirect, dict):
        return (redirect.get('checkout_url') or redirect.get('url') or '').strip()
    return None


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
