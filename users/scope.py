"""Query helpers scoped to the authenticated user's account and company."""

from __future__ import annotations

from users.models import User
from users.company_access import effective_company_id


def users_for_user(user, *, company_id: int | None = None):
    """
    Users visible to ``user``.

    Scoped to the account. ``company_id`` is honored only with Change Company
    read/write; otherwise results are limited to ``user.company_id``.
    """
    qs = User.objects.filter(account_id=user.account_id)
    cid = effective_company_id(user, company_id)
    if cid is None:
        return qs.none()
    return qs.filter(company_id=cid)
