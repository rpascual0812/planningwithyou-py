"""Per-request timezone from the active company (``companies.timezone``)."""

from __future__ import annotations

import json

from django.utils import timezone as dj_timezone

from companies.timezone import UTC, zoneinfo_for_company_id
from users.company_access import effective_company_id

MUTATING_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})


def request_company_id(request) -> int | None:
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return None

    requested = _parse_company_id(_company_id_from_query(request))
    if requested is None and request.method in MUTATING_METHODS:
        requested = _parse_company_id(_company_id_from_body(request))

    return effective_company_id(user, requested)


def _parse_company_id(raw: str) -> int | None:
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _company_id_from_query(request) -> str:
    return request.GET.get('company_id', '').strip()


def _company_id_from_body(request) -> str:
    content_type = (request.META.get('CONTENT_TYPE') or '').split(';', 1)[0].strip().lower()
    if content_type == 'application/json':
        try:
            body = request.body
            if not body:
                return ''
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return ''
        if isinstance(payload, dict):
            value = payload.get('company_id')
            if value is not None and value != '':
                return str(value).strip()
        return ''
    if content_type in ('application/x-www-form-urlencoded', 'multipart/form-data'):
        return (request.POST.get('company_id') or '').strip()
    return ''


class CompanyTimezoneMiddleware:
    """
    For authenticated requests, activate the effective company's timezone so
    ``timezone.now()``, ``timezone.localdate()``, and ORM timestamps use
    company-local time. Unauthenticated requests keep UTC.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return self.get_response(request)

        company_id = request_company_id(request)
        tz = zoneinfo_for_company_id(company_id) if company_id else UTC
        with dj_timezone.override(tz):
            return self.get_response(request)
