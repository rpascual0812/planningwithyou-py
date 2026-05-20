"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from .models import EmailLog


def email_logs_for_user(user):
    """Email logs for the user's account, scoped to their company."""
    return EmailLog.objects.filter(
        account_id=user.account_id,
        company_id=user.company_id,
    )
