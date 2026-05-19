"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from bookings.models import BookingItem


def bookings_for_user(user):
    """Base queryset for booking items visible to ``user``."""
    return BookingItem.objects.filter(
        account_id=user.account_id,
        company_id=user.company_id,
    )
