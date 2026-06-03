"""Resolve company context for ``EmailLog`` timestamps."""

from __future__ import annotations

from emails.models import EmailLog


def email_log_company_id(log: EmailLog) -> int | None:
    """Company pk used for ``email_logs`` created_at / sent_at timezone."""
    if log.company_id:
        return int(log.company_id)

    created_by = getattr(log, 'created_by', None)
    if created_by is not None and getattr(created_by, 'company_id', None):
        return int(created_by.company_id)

    if log.created_by_id:
        from django.contrib.auth import get_user_model

        company_id = (
            get_user_model()
            .objects.filter(pk=log.created_by_id)
            .values_list('company_id', flat=True)
            .first()
        )
        if company_id:
            return int(company_id)
    return None
