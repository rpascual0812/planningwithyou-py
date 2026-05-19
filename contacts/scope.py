"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from contacts.models import Contact


def contacts_for_user(user):
    """Base queryset for contacts visible to ``user``."""
    return Contact.objects.filter(
        account_id=user.account_id,
        company_org_id=user.company_id,
    )
