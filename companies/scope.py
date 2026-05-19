"""Helpers for resolving and scoping tenant companies."""

from __future__ import annotations

from companies.models import Company


def main_company_for_account(account_id: int) -> Company | None:
    company = (
        Company.objects.filter(
            account_id=account_id,
            is_main=True,
            deleted_at__isnull=True,
        )
        .order_by('id')
        .first()
    )
    if company is not None:
        return company
    return (
        Company.objects.filter(
            account_id=account_id,
            deleted_at__isnull=True,
        )
        .order_by('sort_order', 'name', 'id')
        .first()
    )


def main_company_id_for_account(account_id: int) -> int | None:
    company = main_company_for_account(account_id)
    return company.pk if company else None


def user_company_id(user) -> int:
    """Return the authenticated user's company id or raise ``ValueError``."""
    company_id = getattr(user, 'company_id', None)
    if not company_id:
        raise ValueError('User is not linked to a company.')
    return company_id


def company_belongs_to_account(company_id: int, account_id: int) -> bool:
    return Company.objects.filter(
        pk=company_id,
        account_id=account_id,
        deleted_at__isnull=True,
    ).exists()
