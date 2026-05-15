from rest_framework import permissions


class HasAccount(permissions.BasePermission):
    """Require an authenticated user with a non-null ``account_id``."""

    message = 'User is not linked to an account.'

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        return getattr(user, 'account_id', None) is not None
