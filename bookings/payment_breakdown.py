"""Aggregate booking payment breakdowns for summaries."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Case, DecimalField, F, Sum, When

from .models import Quotation
from .payment_validity import valid_booking_payments_queryset

TWOPLACES = Decimal('0.01')


def _booking_credit_amount_field():
    """SQL expression: ``base_amount`` when set, else legacy ``amount``."""
    return Case(
        When(base_amount__gt=0, then=F('base_amount')),
        default=F('amount'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def booking_payments_paid_base_total(quotation_id: int) -> Decimal:
    """Sum of quote portions credited from successful ``booking_payments``."""
    agg = valid_booking_payments_queryset().filter(quotation_id=quotation_id).aggregate(
        total=Sum(_booking_credit_amount_field()),
    )
    return (agg['total'] or Decimal('0')).quantize(TWOPLACES)


def booking_payment_fee_totals(quotation_id: int) -> dict[str, Decimal]:
    qs = valid_booking_payments_queryset().filter(quotation_id=quotation_id)
    agg = qs.aggregate(
        charge_total=Sum('charge_amount'),
        processing_total=Sum('processing_fee'),
        platform_total=Sum('platform_fee'),
        net_total=Sum('net_amount'),
    )
    return {
        'charge_total': (agg['charge_total'] or Decimal('0')).quantize(TWOPLACES),
        'processing_total': (agg['processing_total'] or Decimal('0')).quantize(TWOPLACES),
        'platform_total': (agg['platform_total'] or Decimal('0')).quantize(TWOPLACES),
        'net_total': (agg['net_total'] or Decimal('0')).quantize(TWOPLACES),
    }


def booking_remaining_balance(booking: Quotation) -> Decimal:
    paid = booking_payments_paid_base_total(booking.pk)
    remaining = (booking.total_amount or Decimal('0')) - paid
    if remaining < Decimal('0'):
        return Decimal('0')
    return remaining.quantize(TWOPLACES)


def booking_is_fully_paid(booking: Quotation) -> bool:
    return booking_remaining_balance(booking) <= Decimal('0')


def booking_payment_summary(booking: Quotation) -> dict[str, str]:
    paid_base = booking_payments_paid_base_total(booking.pk)
    fees = booking_payment_fee_totals(booking.pk)
    total = booking.total_amount or Decimal('0')
    remaining = booking_remaining_balance(booking)
    downpayment = booking.required_downpayment_amount or Decimal('0')
    return {
        'total_amount': str(total),
        'required_downpayment_amount': str(downpayment),
        'paid_amount': str(paid_base),
        'paid_charge_amount': str(fees['charge_total']),
        'paid_processing_fees': str(fees['processing_total']),
        'paid_platform_fees': str(fees['platform_total']),
        'paid_net_amount': str(fees['net_total']),
        'remaining_amount': str(remaining),
        'has_paid_payment': paid_base > Decimal('0'),
    }
