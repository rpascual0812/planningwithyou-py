"""Write rows to the ``history`` table."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from bookings.models import History


def actor_id_for_user(user) -> int | None:
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    return user.pk


def record_resource_history(
    *,
    account_id: int,
    resource_type: str,
    resource_id: int,
    action: str,
    changes: dict[str, Any],
    actor=None,
    entity_type: str = '',
    entity_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    booking_id: int | None = None,
) -> History | None:
    if not changes and action == History.Action.UPDATE:
        return None
    payload = dict(metadata or {})
    payload.setdefault('recorded_at', timezone.now().isoformat())
    resolved_entity_type = entity_type or resource_type
    return History.objects.create(
        account_id=account_id,
        resource_type=resource_type,
        resource_id=resource_id,
        booking_id=booking_id,
        entity_type=resolved_entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id_for_user(actor),
        changes=changes,
        metadata=payload,
    )


def record_resource_create(
    *,
    account_id: int,
    resource_type: str,
    resource_id: int,
    snapshot: dict[str, Any],
    actor=None,
    metadata: dict[str, Any] | None = None,
    booking_id: int | None = None,
) -> History:
    return record_resource_history(
        account_id=account_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=History.Action.CREATE,
        changes={'snapshot': snapshot},
        actor=actor,
        metadata=metadata,
        booking_id=booking_id,
    )


def record_resource_update(
    *,
    account_id: int,
    resource_type: str,
    resource_id: int,
    changes: dict[str, Any],
    actor=None,
    metadata: dict[str, Any] | None = None,
    replace: bool = False,
    booking_id: int | None = None,
) -> History | None:
    if not changes:
        return None
    action = History.Action.REPLACE if replace else History.Action.UPDATE
    return record_resource_history(
        account_id=account_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        changes=changes,
        actor=actor,
        metadata=metadata,
        booking_id=booking_id,
    )


def record_resource_delete(
    *,
    account_id: int,
    resource_type: str,
    resource_id: int,
    changes: dict[str, Any],
    actor=None,
    metadata: dict[str, Any] | None = None,
    booking_id: int | None = None,
) -> History:
    meta = dict(metadata or {})
    meta['resource_id'] = resource_id
    return record_resource_history(
        account_id=account_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=History.Action.DELETE,
        changes=changes,
        actor=actor,
        metadata=meta,
        booking_id=booking_id,
    )


def record_resource_field_updates(
    *,
    account_id: int,
    resource_type: str,
    resource_id: int,
    field_changes: dict[str, dict[str, Any]],
    actor=None,
    metadata: dict[str, Any] | None = None,
    booking_id: int | None = None,
) -> History | None:
    if not field_changes:
        return None
    return record_resource_history(
        account_id=account_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=History.Action.UPDATE,
        changes={'fields': field_changes},
        actor=actor,
        metadata=metadata,
        booking_id=booking_id,
    )
