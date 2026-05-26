"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from users.roles import has_feature_read, has_feature_write

from .models import EmailLog


def email_logs_for_user(user, *, company_id=None):
    """
    Email logs visible to ``user``.

    Scoped to the user's account. Users with ``emails`` write may list all
    companies in the account or filter by ``company_id``. Others only see their
    own company; a ``company_id`` query param is ignored unless it matches
    ``user.company_id``.
    """
    qs = EmailLog.objects.filter(account_id=user.account_id)
    if has_feature_write(user, 'emails'):
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs
    if user.company_id is None:
        return qs.filter(company_id__isnull=True)
    effective_company_id = user.company_id
    if company_id is not None and company_id == user.company_id:
        effective_company_id = company_id
    return qs.filter(company_id=effective_company_id)


def email_logs_for_platform_admin(user, *, company_id=None):
    """Cross-tenant email logs for Admin → Emails (``admin_emails`` read/write)."""
    if not has_feature_read(user, 'admin_emails'):
        return EmailLog.objects.none()
    qs = EmailLog.objects.all().order_by('-created_at')
    if company_id is not None:
        qs = qs.filter(company_id=company_id)
    return qs
