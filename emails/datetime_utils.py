"""Backward-compatible imports — prefer ``companies.datetime_utils``."""

from companies.datetime_utils import (  # noqa: F401
    company_timezone_name_for_id,
    company_timezone_name_for_instance,
    datetime_iso_for_instance,
    datetime_iso_in_company_timezone,
)
from emails.timezone_helpers import email_log_company_id


def company_timezone_name_for_email_log(log) -> str:
    return company_timezone_name_for_id(email_log_company_id(log))


def email_log_datetime_iso(value, company_id: int | None) -> str | None:
    return datetime_iso_in_company_timezone(value, company_id)


def email_log_datetime_iso_for_instance(log, field: str) -> str | None:
    return datetime_iso_for_instance(getattr(log, field, None), log)
