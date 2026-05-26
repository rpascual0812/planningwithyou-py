"""Helpers for cross-company context switching (Change Company permission)."""

from __future__ import annotations

from companies.scope import company_belongs_to_account
from users.roles import feature_access_level, has_feature_read

CHANGE_COMPANY_KEY = 'change_company'


def can_change_company(user) -> bool:
    """
    True when the user may select another company in the account.

    Both ``read`` and ``write`` on Change Company allow fetching (GET) and
    switching company context; only ``write`` is required for mutating company
    records on endpoints that use this feature directly.
    """
    return has_feature_read(user, CHANGE_COMPANY_KEY)


def change_company_access_level(user) -> str:
    """``read``, ``write``, or ``none`` for the Change Company feature."""
    return feature_access_level(user, CHANGE_COMPANY_KEY)


def effective_company_id(user, requested_company_id: int | None) -> int | None:
    """
    Company id to use for queries and creates.

    Without Change Company, always returns ``user.company_id``.
    With permission, honors ``requested_company_id`` when it belongs to the account.
    """
    user_company_id = getattr(user, 'company_id', None)
    if not can_change_company(user):
        return user_company_id

    if requested_company_id is None:
        return user_company_id

    account_id = getattr(user, 'account_id', None)
    if (
        account_id is not None
        and company_belongs_to_account(requested_company_id, account_id)
    ):
        return requested_company_id
    return user_company_id
