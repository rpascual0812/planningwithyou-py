"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from contacts.models import Contact
from users.company_access import is_company_context_locked


def contacts_for_user(user, *, company_id: int | None = None):
    """Contacts visible to ``user`` (account-wide unless impersonation is locked)."""
    qs = Contact.objects.filter(account_id=user.account_id)
    if is_company_context_locked(user):
        user_company_id = getattr(user, 'company_id', None)
        if user_company_id is None:
            return qs.none()
        return qs.filter(company_org_id=user_company_id)
    return qs
