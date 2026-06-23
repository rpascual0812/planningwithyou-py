"""Account-wide active user counts vs subscription team_seats."""

from __future__ import annotations

from subscriptions.account_plan import (
    active_account_subscription,
    active_subscription_plan_for_account,
)
from subscriptions.plans import FREE_PLAN

from .models import User

DEFAULT_TEAM_SEATS = 1
REGISTRATION_FREE_USER_SLOTS = 1

SEAT_LIMIT_MESSAGE = (
    'You have reached the maximum number of users allowed on your plan. '
    'Update your subscription under Account Settings to add more users.'
)


def active_users_for_account(account_id: int):
    return User.objects.filter(
        account_id=account_id,
        is_active=True,
        deleted_at__isnull=True,
    )


def active_user_count_for_account(account_id: int) -> int:
    return active_users_for_account(account_id).count()


def paid_team_seats_for_account(account_id: int) -> int:
    """Paid seats purchased on the active subscription (0 on Free)."""
    row = active_account_subscription(account_id)
    if row is None or row.subscription.plan == FREE_PLAN:
        return 0
    return row.team_seats


def allowed_users_for_account(account_id: int) -> int:
    """Paid seats plus the registration user; Free plan is always 1 user only."""
    if active_subscription_plan_for_account(account_id) == FREE_PLAN:
        return DEFAULT_TEAM_SEATS
    row = active_account_subscription(account_id)
    if row is None:
        return DEFAULT_TEAM_SEATS
    return row.team_seats + REGISTRATION_FREE_USER_SLOTS


def team_seats_for_account(account_id: int) -> int:
    """Allowed active users shown in Users and enforced on create/activate."""
    return allowed_users_for_account(account_id)


def account_at_user_seat_limit(account_id: int) -> bool:
    return active_user_count_for_account(account_id) >= allowed_users_for_account(
        account_id,
    )
