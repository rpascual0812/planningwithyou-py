"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from users.models import User


def users_for_user(user):
    """Base queryset for users visible to ``user``."""
    return User.objects.filter(
        account_id=user.account_id,
        company_id=user.company_id,
    )
