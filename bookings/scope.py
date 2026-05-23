"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from django.db.models import Q

from bookings.models import BookingItem
from rest_framework.exceptions import PermissionDenied


def bookings_for_user(user):
    """
    Bookings visible to ``user``:

    - Same account and owned by the user's company (``bookings.company_id``), or
    - Any account where a line references the user's company
      (``booking_items.company_id``), e.g. a supplier on a tenant's booking.
    """
    company_id = user.company_id
    account_id = user.account_id
    return (
        BookingItem.objects.filter(
            Q(account_id=account_id, company_id=company_id)
            | Q(lines__company_id=company_id),
        )
        .distinct()
    )


def booking_user_can_edit(booking: BookingItem, user) -> bool:
    """True when the user's company owns the booking (``bookings.company_id``)."""
    return booking.company_id == user.company_id


def assert_booking_editable(booking: BookingItem, user) -> None:
    if not booking_user_can_edit(booking, user):
        raise PermissionDenied(
            'You can only change bookings owned by your company.',
        )
