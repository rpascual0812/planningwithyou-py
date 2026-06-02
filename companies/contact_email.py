"""Helpers for company contact email defaults."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Company


def first_company_user_email(company_id: int) -> str:
    """Email of the earliest-created user for ``company_id`` (by primary key)."""
    from users.models import User

    email = (
        User.objects.filter(company_id=company_id, deleted_at__isnull=True)
        .order_by('id')
        .values_list('email', flat=True)
        .first()
    )
    return (email or '').strip()


def company_contact_email_address(company: Company) -> str:
    """Primary company contact inbox: ``contact_email``, else first user."""
    stored = (company.contact_email or '').strip()
    if stored:
        return stored
    return first_company_user_email(company.pk)
