"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from .models import EmailLog


def email_logs_for_user(user, *, company_id=None):
    """
    Email logs visible to ``user``.

    Scoped to the user's account. Account admins may list all companies in the
    account or filter by ``company_id``. Other users only see their own company;
    a ``company_id`` query param is ignored unless it matches ``user.company_id``.
    """
    qs = EmailLog.objects.filter(account_id=user.account_id)
    if getattr(user, 'is_admin', False):
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs
    effective_company_id = user.company_id
    if company_id is not None and company_id == user.company_id:
        effective_company_id = company_id
    return qs.filter(company_id=effective_company_id)
