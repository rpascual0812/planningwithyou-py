"""Shared helpers for user/RBAC tests."""

from __future__ import annotations

from users.models import RolePermission
from users.roles import ADMIN_FEATURE_KEYS, ensure_owner_role


def assign_owner_role(user) -> None:
    role = ensure_owner_role(user.account)
    user.role = role
    user.save(update_fields=['role_id'])


def grant_platform_admin(user) -> None:
    if user.role_id is None:
        assign_owner_role(user)
    for feature_key in ADMIN_FEATURE_KEYS:
        RolePermission.objects.update_or_create(
            role_id=user.role_id,
            feature_key=feature_key,
            defaults={'access': 'write'},
        )
