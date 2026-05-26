"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from users.company_access import effective_company_id
from users.roles import has_feature_read

from .models import EmailLog


def email_logs_for_user(user, *, company_id=None):
    """
    Email logs visible to ``user``.

    Scoped to the account. ``company_id`` is honored only with Change Company;
    otherwise logs are limited to ``user.company_id``.
    """
    qs = EmailLog.objects.filter(account_id=user.account_id)
    cid = effective_company_id(user, company_id)
    if cid is None:
        return qs.filter(company_id__isnull=True)
    return qs.filter(company_id=cid)


def email_logs_for_platform_admin(user, *, company_id=None):
    """Cross-tenant email logs for Admin → Emails (``admin_emails`` read/write)."""
    if not has_feature_read(user, 'admin_emails'):
        return EmailLog.objects.none()
    qs = EmailLog.objects.all().order_by('-created_at')
    if company_id is not None:
        qs = qs.filter(company_id=company_id)
    return qs
