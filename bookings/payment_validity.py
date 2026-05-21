"""Rules for whether a booking payment counts toward supplier capacity."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Q, QuerySet

from .models import BookingPayment

# Statuses that do not count as a successful client payment.
_INVALID_PAYMENT_STATUSES = frozenset({
    'failed',
    'cancelled',
    'canceled',
    'void',
    'refunded',
    'pending',
    'processing',
})


def is_valid_booking_payment(payment: BookingPayment) -> bool:
    """Return True when a payment row should reserve supplier capacity."""
    if payment.deleted_at is not None:
        return False
    if payment.amount is None or payment.amount <= Decimal('0'):
        return False
    status = (payment.transaction_status or '').strip().lower()
    if status in _INVALID_PAYMENT_STATUSES:
        return False
    return True


def valid_booking_payments_queryset() -> QuerySet[BookingPayment]:
    """Non-deleted payments with positive amount and a non-failed status."""
    qs = BookingPayment.objects.filter(
        deleted_at__isnull=True,
        amount__gt=0,
    )
    status_filters = Q()
    for invalid in _INVALID_PAYMENT_STATUSES:
        status_filters |= Q(transaction_status__iexact=invalid)
    return qs.exclude(status_filters)


def booking_has_valid_payment(booking_id: int) -> bool:
    return valid_booking_payments_queryset().filter(booking_id=booking_id).exists()
