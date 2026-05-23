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
    """Require an authenticated platform administrator."""

    message = 'Admin access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user.is_authenticated and getattr(user, 'is_admin', False),
        )


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
