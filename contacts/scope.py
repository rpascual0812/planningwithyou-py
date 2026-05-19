"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from contacts.models import Contact


def contacts_for_user(user):
    """Base queryset for contacts visible to ``user`` (all companies on the account)."""
    return Contact.objects.filter(account_id=user.account_id)
