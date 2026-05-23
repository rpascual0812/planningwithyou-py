"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from .models import EmailLog


def email_logs_for_user(user, *, company_id=None):
    """
    Email logs visible to ``user``.

    Admins see all logs, optionally filtered by ``company_id`` (no account filter).
    Other users are scoped to their account and company; ``company_id`` is ignored.
    """
    if getattr(user, 'is_admin', False):
        qs = EmailLog.objects.all()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs
    return EmailLog.objects.filter(
        account_id=user.account_id,
        company_id=user.company_id,
    )
