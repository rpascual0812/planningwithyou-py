"""Query helpers scoped to the authenticated user's account and company."""

from __future__ import annotations

from companies.scope import company_belongs_to_account

from users.models import User
from users.roles import has_feature_write


def users_for_user(user, *, company_id: int | None = None):
    """
    Users visible to ``user``.

    Scoped to the user's account. Users with ``users`` write may filter by
    ``company_id`` when it belongs to the account. Others only see their own
    company; a ``company_id`` query param is ignored unless it matches
    ``user.company_id``.
    """
    qs = User.objects.filter(account_id=user.account_id)
    if has_feature_write(user, 'users'):
        if company_id is not None:
            if company_belongs_to_account(company_id, user.account_id):
                qs = qs.filter(company_id=company_id)
            else:
                qs = qs.none()
        return qs
    if user.company_id is None:
        return qs.none()
    effective_company_id = user.company_id
    if company_id is not None and company_id == user.company_id:
        effective_company_id = company_id
    return qs.filter(company_id=effective_company_id)
