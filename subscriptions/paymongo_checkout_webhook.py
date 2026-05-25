"""Apply one-time PayMongo checkout payments for subscription seat upgrades."""

from __future__ import annotations

import logging

from django.db import transaction

from bookings.paymongo_webhook import normalize_paymongo_webhook_body

from .models import AccountSubscription, Subscription
from .paymongo_subscriptions import update_account_subscription_recurring_plan
from .proration import apply_subscription_selection

logger = logging.getLogger(__name__)

CHECKOUT_KIND_SEAT_UPGRADE = 'subscription_seat_upgrade'


def _metadata_from_checkout_event(event: dict) -> dict[str, str]:
    data = event.get('data')
    if not isinstance(data, dict):
        return {}
    attrs = data.get('attributes')
    if not isinstance(attrs, dict):
        return {}
    for candidate in (
        attrs.get('metadata'),
        (attrs.get('data') or {}).get('attributes', {}).get('metadata')
        if isinstance(attrs.get('data'), dict)
        else None,
    ):
        if isinstance(candidate, dict):
            return {str(k): str(v) for k, v in candidate.items()}
    return {}


@transaction.atomic
def _apply_seat_upgrade(
    *,
    account_sub: AccountSubscription,
    team_seats: int,
    subscription: Subscription,
) -> None:
    apply_subscription_selection(account_sub, subscription, team_seats)
    if not update_account_subscription_recurring_plan(
        account_sub,
        subscription,
        team_seats,
    ):
        logger.warning(
            'Seat upgrade saved locally but PayMongo recurring amount was not updated '
            '(account_subscription=%s). Enable subscription payment methods in PayMongo or '
            'update the subscription manually.',
            account_sub.uuid,
        )


def handle_subscription_checkout_webhook_body(body: dict) -> bool:
    handled = False
    for event in normalize_paymongo_webhook_body(body):
        if handle_subscription_checkout_webhook_event(event):
            handled = True
    return handled


def handle_subscription_checkout_webhook_event(event: dict) -> bool:
    event_type = (event.get('type') or '').strip()
    if event_type not in {'checkout.session.completed', 'payment.paid'}:
        return False

    metadata = _metadata_from_checkout_event(event)
    if metadata.get('kind') != CHECKOUT_KIND_SEAT_UPGRADE:
        return False

    try:
        account_sub_id = int(metadata['account_subscription_id'])
        team_seats = int(metadata['team_seats'])
        subscription_id = int(metadata['subscription_id'])
    except (KeyError, TypeError, ValueError):
        return False

    account_sub = (
        AccountSubscription.objects.select_related('subscription', 'account')
        .filter(pk=account_sub_id, deleted_at__isnull=True)
        .first()
    )
    subscription = Subscription.objects.filter(pk=subscription_id).first()
    if account_sub is None or subscription is None:
        return False

    _apply_seat_upgrade(
        account_sub=account_sub,
        team_seats=team_seats,
        subscription=subscription,
    )
    return True
