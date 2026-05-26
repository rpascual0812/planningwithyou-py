from rest_framework import permissions

from companies.scope import company_belongs_to_account


class HasAccount(permissions.BasePermission):
    """Require an authenticated user with a non-null ``account_id``."""

    message = 'User is not linked to an account.'

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        return getattr(user, 'account_id', None) is not None


class IsAdmin(permissions.BasePermission):
    """Require an authenticated platform administrator (``platform_admin`` write)."""

    message = 'Admin access required.'

    def has_permission(self, request, view):
        from users.roles import is_platform_admin

        user = request.user
        return bool(user.is_authenticated and is_platform_admin(user))


class HasCompany(permissions.BasePermission):
    """Require an authenticated user with a company in their account."""

    message = 'User is not linked to a company.'

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        account_id = getattr(user, 'account_id', None)
        company_id = getattr(user, 'company_id', None)
        if account_id is None or company_id is None:
            return False
        return company_belongs_to_account(company_id, account_id)


class FeatureAccess(permissions.BasePermission):
    """
    Enforce per-feature access:
    - safe methods require read/write
    - unsafe methods require write

    View must declare `feature_key` or implement `get_feature_key(request)`.
    """

    message = 'Insufficient permissions.'

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        feature_key = None
        if hasattr(view, 'get_feature_key'):
            feature_key = view.get_feature_key(request)
        if not feature_key:
            feature_key = getattr(view, 'feature_key', '') or ''
        if not feature_key:
            # If a view didn't declare a feature, do not block by default.
            return True

        from users.roles import (
            effective_feature_permissions,
            feature_access_level_for_request,
        )

        access = getattr(user, '_effective_feature_access', None)
        if access is None:
            access = effective_feature_permissions(user)
            setattr(user, '_effective_feature_access', access)

        safe = request.method in permissions.SAFE_METHODS
        level = feature_access_level_for_request(
            user,
            feature_key,
            safe_method=safe,
        )
        if safe:
            return level in ('read', 'write')
        return level == 'write'
