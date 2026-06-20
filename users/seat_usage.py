"""Account-wide active user counts vs subscription team_seats."""

from __future__ import annotations

from subscriptions.account_plan import active_account_subscription

from .models import User

DEFAULT_TEAM_SEATS = 1

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


def team_seats_for_account(account_id: int) -> int:
    row = active_account_subscription(account_id)
    if row is None:
        return DEFAULT_TEAM_SEATS
    return row.team_seats


def account_at_user_seat_limit(account_id: int) -> bool:
    return active_user_count_for_account(account_id) >= team_seats_for_account(
        account_id,
    )
