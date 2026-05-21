"""Booking payment balances for checkout link generation."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from .models import BookingItem, BookingPaymentLink


def booking_paid_base_total(booking_id: int) -> Decimal:
    """Sum of ``base_amount`` on paid payment links (quote portion collected)."""
    agg = BookingPaymentLink.objects.filter(
        booking_id=booking_id,
        status=BookingPaymentLink.Status.PAID,
    ).aggregate(total=Sum('base_amount'))
    return agg['total'] or Decimal('0')


def booking_remaining_balance(booking: BookingItem) -> Decimal:
    paid = booking_paid_base_total(booking.pk)
    remaining = (booking.total_amount or Decimal('0')) - paid
    if remaining < Decimal('0'):
        return Decimal('0')
    return remaining


def booking_is_fully_paid(booking: BookingItem) -> bool:
    return booking_remaining_balance(booking) <= Decimal('0')


def booking_payment_summary(booking: BookingItem) -> dict[str, str]:
    paid = booking_paid_base_total(booking.pk)
    total = booking.total_amount or Decimal('0')
    remaining = booking_remaining_balance(booking)
    downpayment = booking.required_downpayment_amount or Decimal('0')
    return {
        'total_amount': str(total),
        'required_downpayment_amount': str(downpayment),
        'paid_amount': str(paid),
        'remaining_amount': str(remaining),
        'has_paid_payment': paid > Decimal('0'),
    }
