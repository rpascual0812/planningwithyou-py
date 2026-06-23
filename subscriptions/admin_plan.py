"""Activate the internal Admin subscription plan (platform staff only)."""

from __future__ import annotations

import logging

from users.models import Account, User
from users.roles import has_platform_admin_read

from .errors import SubscriptionCheckoutError
from .lifecycle import ensure_account_subscription_row, get_account_subscription_row
from .models import AccountSubscription, Subscription
from .paymongo_subscriptions import cancel_paymongo_subscription
from .plans import ADMIN_PLAN, PAID_PLAN_SLUGS

logger = logging.getLogger(__name__)


def subscribe_account_to_admin_plan(
    *,
    account: Account,
    user: User,
    billing_cycle: str = Subscription.BillingCycle.MONTHLY,
    team_seats: int = 1,
) -> AccountSubscription:
    if not has_platform_admin_read(user):
        raise SubscriptionCheckoutError('Admin plan is not available.')
    if billing_cycle not in Subscription.BillingCycle.values:
        raise SubscriptionCheckoutError('Invalid billing cycle.')

    admin_sub = Subscription.objects.filter(
        plan=ADMIN_PLAN,
        billing_cycle=billing_cycle,
        is_active=True,
        is_selectable=True,
    ).first()
    if admin_sub is None:
        raise SubscriptionCheckoutError('Admin plan is not available.')

    current = get_account_subscription_row(account.pk)
    if current is not None and current.subscription.plan == ADMIN_PLAN:
        raise SubscriptionCheckoutError('You are already on the Admin plan.')

    if current is not None:
        paymongo_id = (current.reference_id or '').strip()
        if paymongo_id and current.subscription.plan in PAID_PLAN_SLUGS:
            try:
                cancel_paymongo_subscription(paymongo_id)
            except Exception as exc:
                logger.warning('PayMongo cancel failed for %s: %s', paymongo_id, exc)

    return ensure_account_subscription_row(
        account=account,
        subscription=admin_sub,
        team_seats=team_seats,
        status=AccountSubscription.Status.ACTIVE,
        reference_id='',
    )
