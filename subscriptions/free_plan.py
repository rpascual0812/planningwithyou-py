"""Schedule or activate Free plan (downgrade keeps paid access until prepaid period ends)."""

from __future__ import annotations

from users.models import Account

from .errors import SubscriptionCheckoutError
from .lifecycle import activate_free_plan
from .models import AccountSubscription, Subscription


def subscribe_account_to_free_plan(
    *,
    account: Account,
    billing_cycle: str = Subscription.BillingCycle.MONTHLY,
) -> AccountSubscription:
    if billing_cycle not in Subscription.BillingCycle.values:
        raise SubscriptionCheckoutError('Invalid billing cycle.')
    return activate_free_plan(account=account, billing_cycle=billing_cycle)
