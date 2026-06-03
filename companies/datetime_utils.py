"""Shared datetime helpers for company-local timestamps."""

from __future__ import annotations

from companies.timezone import (
    normalize_company_timezone_name,
    zoneinfo_for_company_id,
    zoneinfo_for_company_timezone,
)


def company_timezone_name_for_id(company_id: int | None) -> str:
    if not company_id:
        return 'UTC'
    from companies.models import Company

    raw = (
        Company.objects.filter(pk=company_id)
        .values_list('timezone', flat=True)
        .first()
    )
    return normalize_company_timezone_name(raw)


def company_timezone_name_for_instance(instance) -> str:
    from companies.timezone import company_id_for_instance

    return company_timezone_name_for_id(company_id_for_instance(instance))


def datetime_iso_in_company_timezone(value, company_id: int | None) -> str | None:
    if value is None:
        return None
    tz = zoneinfo_for_company_id(company_id)
    return value.astimezone(tz).isoformat()


def datetime_iso_for_instance(value, instance) -> str | None:
    if value is None:
        return None
    tz_name = company_timezone_name_for_instance(instance)
    tz = zoneinfo_for_company_timezone(tz_name)
    return value.astimezone(tz).isoformat()
