"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from calendars.models import Calendar, CalendarStatus


def calendar_statuses_for_user(user):
    return CalendarStatus.objects.filter(account_id=user.account_id)


def calendar_events_for_user(user):
    return Calendar.objects.filter(
        account_id=user.account_id,
        company_id=user.company_id,
    )
