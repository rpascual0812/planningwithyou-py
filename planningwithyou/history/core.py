"""Low-level diff helpers for history ``changes`` JSON."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def field_change(old: Any, new: Any) -> dict[str, Any] | None:
    old_json = json_value(old)
    new_json = json_value(new)
    if old_json == new_json:
        return None
    return {'old': old_json, 'new': new_json}


def diff_field_map(
    old: dict[str, Any],
    new: dict[str, Any],
    fields: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    changes = {}
    for field in fields:
        delta = field_change(old.get(field), new.get(field))
        if delta is not None:
            changes[field] = delta
    return changes


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


def request_metadata(request) -> dict[str, Any]:
    if request is None:
        return {'source': 'system'}
    return {
        'source': 'api',
        'method': getattr(request, 'method', ''),
        'path': getattr(request, 'path', ''),
    }
