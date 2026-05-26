"""Record and diff booking changes in the ``history`` table."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone

from planningwithyou.history.core import field_change as _field_change
from planningwithyou.history.core import request_metadata
from planningwithyou.history.record import (
    record_resource_history,
)

from .models import BookingGroup, BookingItem, BookingLine, History

User = get_user_model()

BOOKING_HEADER_FIELDS = (
    'title',
    'status_id',
    'contact_id',
    'date_of_event',
    'total_amount',
    'required_downpayment_amount',
    'notes',
    'sort_order',
)

LINE_SNAPSHOT_FIELDS = (
    'label',
    'group_name',
    'field_type',
    'is_required',
    'price',
    'required_downpayment',
    'value',
    'company_id',
    'tier_id',
    'package_version_id',
    'sort_order',
)


def _json_value(value: Any) -> Any:  # noqa: F811 — local alias for booking snapshots
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def snapshot_booking_header(booking: BookingItem) -> dict[str, Any]:
    return {field: _json_value(getattr(booking, field)) for field in BOOKING_HEADER_FIELDS}


def snapshot_groups(booking: BookingItem) -> list[dict[str, Any]]:
    groups = []
    for group in booking.groups.all().order_by('id'):
        groups.append({'id': group.pk, 'name': group.name})
    return groups


def snapshot_line(line: BookingLine) -> dict[str, Any]:
    group_name = line.booking_group.name if line.booking_group_id else ''
    data = {
        'id': line.pk,
        'group_name': group_name,
    }
    for field in LINE_SNAPSHOT_FIELDS:
        if field == 'group_name':
            continue
        data[field] = _json_value(getattr(line, field))
    return data


def snapshot_lines(booking: BookingItem) -> list[dict[str, Any]]:
    lines = []
    for line in booking.lines.select_related('booking_group').order_by('sort_order', 'id'):
        lines.append(snapshot_line(line))
    return lines


def snapshot_booking_full(booking: BookingItem) -> dict[str, Any]:
    return {
        'booking': snapshot_booking_header(booking),
        'groups': snapshot_groups(booking),
        'lines': snapshot_lines(booking),
    }


def line_identity_key(line: dict[str, Any]) -> str:
    return '|'.join(
        [
            str(line.get('group_name') or ''),
            str(line.get('label') or ''),
            str(line.get('sort_order') or 0),
        ],
    )


def diff_field_map(
    old: dict[str, Any],
    new: dict[str, Any],
    fields: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    changes = {}
    for field in fields:
        delta = _field_change(old.get(field), new.get(field))
        if delta is not None:
            changes[field] = delta
    return changes


def diff_booking_header(old: dict[str, Any], new: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return diff_field_map(old, new, BOOKING_HEADER_FIELDS)


def diff_named_rows(
    old_rows: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
    *,
    name_key: str,
) -> dict[str, Any]:
    old_names = {row[name_key] for row in old_rows}
    new_names = {row[name_key] for row in new_rows}
    return {
        'added': sorted(new_names - old_names),
        'removed': sorted(old_names - new_names),
    }


def diff_lines(
    old_lines: list[dict[str, Any]],
    new_lines: list[dict[str, Any]],
) -> dict[str, Any]:
    old_by_key = {line_identity_key(line): line for line in old_lines}
    new_by_key = {line_identity_key(line): line for line in new_lines}
    old_keys = set(old_by_key)
    new_keys = set(new_by_key)

    added = [new_by_key[key] for key in sorted(new_keys - old_keys)]
    removed = [old_by_key[key] for key in sorted(old_keys - new_keys)]
    changed = []
    for key in sorted(old_keys & new_keys):
        field_changes = diff_field_map(
            old_by_key[key],
            new_by_key[key],
            LINE_SNAPSHOT_FIELDS,
        )
        if field_changes:
            changed.append(
                {
                    'key': key,
                    'label': new_by_key[key].get('label'),
                    'group_name': new_by_key[key].get('group_name'),
                    'fields': field_changes,
                },
            )

    return {
        'added': added,
        'removed': removed,
        'changed': changed,
    }


def build_update_changes(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    include_nested: bool,
) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    header_changes = diff_booking_header(before['booking'], after['booking'])
    if header_changes:
        changes['booking'] = header_changes

    if include_nested:
        group_changes = diff_named_rows(before['groups'], after['groups'], name_key='name')
        if group_changes['added'] or group_changes['removed']:
            changes['groups'] = group_changes
        line_changes = diff_lines(before['lines'], after['lines'])
        if line_changes['added'] or line_changes['removed'] or line_changes['changed']:
            changes['lines'] = line_changes
    return changes


def record_booking_history(
    *,
    booking: BookingItem,
    action: str,
    entity_type: str,
    changes: dict[str, Any],
    actor=None,
    entity_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> History | None:
    return record_resource_history(
        account_id=booking.account_id,
        resource_type=History.ResourceType.BOOKING,
        resource_id=booking.pk,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
        actor=actor,
        metadata=metadata,
        booking_id=booking.pk,
    )


def record_booking_create(
    booking: BookingItem,
    *,
    actor=None,
    metadata: dict[str, Any] | None = None,
) -> History:
    return record_booking_history(
        booking=booking,
        action=History.Action.CREATE,
        entity_type=History.EntityType.BOOKING,
        entity_id=booking.pk,
        changes={'snapshot': snapshot_booking_full(booking)},
        actor=actor,
        metadata=metadata,
    )


def record_booking_update(
    booking: BookingItem,
    before: dict[str, Any],
    *,
    actor=None,
    include_nested: bool = False,
    metadata: dict[str, Any] | None = None,
) -> History | None:
    after = snapshot_booking_full(booking)
    changes = build_update_changes(before, after, include_nested=include_nested)
    if not changes:
        return None
    action = History.Action.REPLACE if include_nested else History.Action.UPDATE
    return record_booking_history(
        booking=booking,
        action=action,
        entity_type=History.EntityType.BOOKING,
        entity_id=booking.pk,
        changes=changes,
        actor=actor,
        metadata=metadata,
    )


def record_booking_delete(
    booking: BookingItem,
    *,
    actor=None,
    metadata: dict[str, Any] | None = None,
) -> History:
    meta = dict(metadata or {})
    meta['booking_id'] = booking.pk
    return record_booking_history(
        booking=booking,
        action=History.Action.DELETE,
        entity_type=History.EntityType.BOOKING,
        entity_id=booking.pk,
        changes={
            'unique_id': _json_value(booking.unique_id),
            'title': _json_value(booking.title),
            'booking_id': booking.pk,
        },
        actor=actor,
        metadata=meta,
    )


def record_group_delete(
    booking: BookingItem,
    group: BookingGroup,
    *,
    actor=None,
    metadata: dict[str, Any] | None = None,
) -> History:
    return record_booking_history(
        booking=booking,
        action=History.Action.DELETE,
        entity_type=History.EntityType.BOOKING_GROUP,
        entity_id=group.pk,
        changes={'name': group.name},
        actor=actor,
        metadata=metadata,
    )


def record_booking_field_updates(
    booking: BookingItem,
    field_changes: dict[str, dict[str, Any]],
    *,
    actor=None,
    metadata: dict[str, Any] | None = None,
) -> History | None:
    if not field_changes:
        return None
    return record_booking_history(
        booking=booking,
        action=History.Action.UPDATE,
        entity_type=History.EntityType.BOOKING,
        entity_id=booking.pk,
        changes={'booking': field_changes},
        actor=actor,
        metadata=metadata,
    )
