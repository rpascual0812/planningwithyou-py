"""Compute RSVP dashboard metrics for the public guest list page."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone as dt_timezone

from django.utils import timezone

from .rsvp_utils import collect_rsvp_elements, normalize_rsvp_fields

ATTENDANCE_FIELD_RE = re.compile(
    r'(attend|attendance|going|rsvp|response|reply|join)',
    re.IGNORECASE,
)
GUEST_COUNT_FIELD_RE = re.compile(
    r'(guest|visitor|party|headcount|pax|seat)',
    re.IGNORECASE,
)
YES_VALUES = {
    'yes',
    'y',
    'will go',
    'going',
    'attending',
    'accept',
    'accepted',
    'joyfully accept',
    'count me in',
}
NO_VALUES = {
    'no',
    'n',
    'will not go',
    "won't go",
    'not going',
    'decline',
    'declined',
    'cannot attend',
    "can't attend",
    'unable to attend',
    'regretfully decline',
}


def _parse_positive_int(raw: object) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        value = int(float(text))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _classify_attendance(value: str) -> str:
    normalized = ' '.join(str(value or '').strip().lower().split())
    if not normalized:
        return 'unknown'
    if normalized in YES_VALUES:
        return 'yes'
    if normalized in NO_VALUES:
        return 'no'
    if any(token in normalized for token in ('not go', 'decline', 'unable', "can't", 'cannot')):
        return 'no'
    if any(token in normalized for token in ('will go', 'going', 'attend', 'accept', 'joy')):
        return 'yes'
    return 'unknown'


def _find_attendance_field_id(fields: list[dict]) -> str | None:
    for field in fields:
        field_id = str(field.get('id') or '').strip()
        if not field_id or field.get('type') != 'select':
            continue
        label = str(field.get('label') or '')
        if ATTENDANCE_FIELD_RE.search(field_id) or ATTENDANCE_FIELD_RE.search(label):
            return field_id
    return None


def _find_guest_count_field_id(fields: list[dict]) -> str | None:
    for field in fields:
        field_id = str(field.get('id') or '').strip()
        if not field_id:
            continue
        label = str(field.get('label') or '')
        if GUEST_COUNT_FIELD_RE.search(field_id) or GUEST_COUNT_FIELD_RE.search(label):
            return field_id
    return None


def _parse_iso_date(raw: object) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = f'{text[:-1]}+00:00'
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed.date()


def _rsvp_deadline(document: dict) -> date | None:
    meta = document.get('meta') if isinstance(document.get('meta'), dict) else {}
    for key in ('rsvpDeadline', 'rsvp_deadline'):
        deadline = _parse_iso_date(meta.get(key))
        if deadline is not None:
            return deadline

    for element in collect_rsvp_elements(document):
        for key in ('rsvpDeadline', 'rsvp_deadline'):
            deadline = _parse_iso_date(element.get(key))
            if deadline is not None:
                return deadline

    return None


def _expected_guest_count(document: dict) -> int | None:
    meta = document.get('meta') if isinstance(document.get('meta'), dict) else {}
    for key in ('expectedGuestCount', 'expected_guest_count'):
        value = _parse_positive_int(meta.get(key))
        if value is not None:
            return value

    for element in collect_rsvp_elements(document):
        for key in ('expectedGuestCount', 'expected_guest_count'):
            value = _parse_positive_int(element.get(key))
            if value is not None:
                return value
    return None


def _merged_rsvp_fields(document: dict) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for element in collect_rsvp_elements(document):
        for field in normalize_rsvp_fields(element):
            field_id = str(field.get('id') or '').strip()
            if not field_id or field_id in seen:
                continue
            seen.add(field_id)
            merged.append(field)
    return merged


def _percent(count: int, total: int) -> int:
    if total <= 0:
        return 0
    return round((count / total) * 100)


def compute_rsvp_analytics(template, submissions: list[dict]) -> dict:
    document = template.document if isinstance(template.document, dict) else {}
    field_config = _merged_rsvp_fields(document)
    attendance_field_id = _find_attendance_field_id(field_config)
    guest_count_field_id = _find_guest_count_field_id(field_config)

    will_go = 0
    will_not_go = 0
    for submission in submissions:
        fields_data = submission.get('fields_data') if isinstance(submission, dict) else {}
        if not isinstance(fields_data, dict):
            fields_data = {}

        guest_count = 1
        if guest_count_field_id:
            guest_count = _parse_positive_int(fields_data.get(guest_count_field_id)) or 1

        if attendance_field_id:
            status = _classify_attendance(str(fields_data.get(attendance_field_id, '')))
            if status == 'yes':
                will_go += guest_count
            elif status == 'no':
                will_not_go += guest_count
            else:
                will_go += guest_count
        else:
            will_go += guest_count

    responded_guests = will_go + will_not_go
    expected = _expected_guest_count(document)
    if expected is None:
        expected = responded_guests
        awaiting_reply = 0
    else:
        awaiting_reply = max(0, expected - responded_guests)

    total_guests = max(expected, responded_guests)
    deadline = _rsvp_deadline(document)
    today = timezone.localdate()
    days_remaining = None
    if deadline is not None:
        days_remaining = max(0, (deadline - today).days)

    breakdown = [
        {
            'key': 'will_go',
            'label': 'Will go',
            'count': will_go,
            'percent': _percent(will_go, total_guests),
        },
        {
            'key': 'will_not_go',
            'label': 'Will not go',
            'count': will_not_go,
            'percent': _percent(will_not_go, total_guests),
        },
        {
            'key': 'awaiting_reply',
            'label': 'Awaiting reply',
            'count': awaiting_reply,
            'percent': _percent(awaiting_reply, total_guests),
        },
    ]

    return {
        'total_views': int(getattr(template, 'view_count', 0) or 0),
        'expected_visitors': expected,
        'days_remaining': days_remaining,
        'will_go': will_go,
        'will_not_go': will_not_go,
        'awaiting_reply': awaiting_reply,
        'total_guests': total_guests,
        'breakdown': breakdown,
    }
