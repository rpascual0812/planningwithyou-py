"""Resolve and activate IANA time zones from ``companies.timezone``."""

from __future__ import annotations

from contextlib import contextmanager
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone as dj_timezone

UTC = ZoneInfo('UTC')


def normalize_company_timezone_name(raw: str | None) -> str:
    """Return a valid IANA name or ``UTC`` when missing/invalid."""
    name = (raw or '').strip()
    if not name:
        return 'UTC'
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return 'UTC'
    return name


def zoneinfo_for_company_timezone(raw: str | None) -> ZoneInfo:
    return ZoneInfo(normalize_company_timezone_name(raw))


def zoneinfo_for_company_id(company_id: int | None) -> ZoneInfo:
    if not company_id:
        return UTC
    from companies.models import Company

    tz_name = (
        Company.objects.filter(pk=company_id)
        .values_list('timezone', flat=True)
        .first()
    )
    return zoneinfo_for_company_timezone(tz_name)


def company_id_for_instance(instance) -> int | None:
    """Best-effort company pk for a model instance about to be saved."""
    from companies.models import Company

    if isinstance(instance, Company):
        return instance.pk

    company_id = getattr(instance, 'company_id', None)
    if company_id:
        return int(company_id)

    company = getattr(instance, 'company', None)
    if company is not None:
        pk = getattr(company, 'pk', None)
        if pk:
            return int(pk)
    return None


def zoneinfo_for_save_instance(instance) -> ZoneInfo:
    """Timezone to use when persisting ``instance`` (insert or update)."""
    from companies.models import Company

    if isinstance(instance, Company):
        return zoneinfo_for_company_timezone(instance.timezone)

    company_id = company_id_for_instance(instance)
    if company_id:
        return zoneinfo_for_company_id(company_id)
    return UTC


def activate_timezone_for_instance(instance) -> ZoneInfo:
    tz = zoneinfo_for_save_instance(instance)
    dj_timezone.activate(tz)
    return tz


def now_in_company_timezone(company_id: int | None):
    """Current moment as an aware datetime in ``companies.timezone`` (UTC if unknown)."""
    tz = zoneinfo_for_company_id(company_id)
    return dj_timezone.now().astimezone(tz)


@contextmanager
def company_timezone(company_id: int | None):
    """Activate ``companies.timezone`` for a block (falls back to UTC)."""
    with dj_timezone.override(zoneinfo_for_company_id(company_id)):
        yield


def activate_company_timezone(company_id: int | None) -> ZoneInfo:
    tz = zoneinfo_for_company_id(company_id)
    dj_timezone.activate(tz)
    return tz
