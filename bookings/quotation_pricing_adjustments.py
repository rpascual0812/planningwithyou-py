"""Discount / override totals for quotations (checkout uses ``total_amount``)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .models import Quotation
from .pricing import resolve_booking_line_price

TWOPLACES = Decimal('0.01')
DISCOUNT_TYPE_PERCENT = 'percent'
DISCOUNT_TYPE_FIXED = 'fixed'
DISCOUNT_TYPES = frozenset({DISCOUNT_TYPE_PERCENT, DISCOUNT_TYPE_FIXED})


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _parse_amount(raw) -> Decimal | None:
    if raw is None or raw == '':
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if value < 0:
        return None
    return value


def sum_quotation_line_subtotal(booking: Quotation) -> Decimal:
    total = Decimal('0')
    for line in booking.lines.all():
        amount = resolve_booking_line_price(line)
        if amount is None or amount <= 0:
            continue
        total += amount
    return _quantize(total)


def apply_quotation_discount(
    subtotal: Decimal,
    discount_amount: Decimal,
    discount_type: str,
) -> Decimal:
    if subtotal <= 0 or discount_amount <= 0:
        return subtotal
    if discount_type == DISCOUNT_TYPE_PERCENT:
        pct = min(discount_amount, Decimal('100'))
        return _quantize(subtotal - (subtotal * pct / Decimal('100')))
    return _quantize(subtotal - discount_amount)


def resolve_quotation_effective_total(booking: Quotation) -> Decimal:
    line_subtotal = sum_quotation_line_subtotal(booking)

    override = booking.total_override_amount
    if override is not None and override >= 0:
        return _quantize(override)

    discount = booking.discount_amount
    discount_type = (booking.discount_type or '').strip()
    if discount is not None and discount > 0 and discount_type in DISCOUNT_TYPES:
        return apply_quotation_discount(line_subtotal, discount, discount_type)

    return line_subtotal


def sync_quotation_total_amount(booking: Quotation) -> Decimal:
    effective = resolve_quotation_effective_total(booking)
    if booking.total_amount != effective:
        booking.total_amount = effective
        booking.save(update_fields=['total_amount', 'updated_at'])
    return effective
