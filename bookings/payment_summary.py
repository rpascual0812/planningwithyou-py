"""Booking payment balances (re-exports from ``payment_breakdown``)."""

from .payment_breakdown import (
    booking_is_fully_paid,
    booking_payment_summary,
    booking_payments_paid_base_total,
    booking_remaining_balance,
)

# Backwards-compatible alias
booking_payments_paid_total = booking_payments_paid_base_total

__all__ = [
    'booking_is_fully_paid',
    'booking_payment_summary',
    'booking_payments_paid_base_total',
    'booking_payments_paid_total',
    'booking_remaining_balance',
]
