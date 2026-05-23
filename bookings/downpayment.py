"""Required downpayment totals from supplier package rows on booking lines."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from .models import BookingItem
from .supplier_line import package_for_supplier_booking_line


def package_required_downpayment_amount(
    company_id: int,
    tier_id: int,
    package_version_id: int | None = None,
) -> Decimal:
    from .supplier_line import _package_query_for_supplier_line

    package = _package_query_for_supplier_line(
        company_id,
        tier_id,
        package_version_id,
    )
    if package is None:
        from users.supplier_price import resolve_active_package_for_supplier_tier

        package = resolve_active_package_for_supplier_tier(company_id, tier_id)
    if package is None:
        return Decimal('0')
    return package.required_downpayment_amount or Decimal('0')


def _line_required_downpayment(line) -> Decimal:
    if line.field_type == 'supplier':
        package = package_for_supplier_booking_line(line)
        if package is not None:
            return package.required_downpayment_amount or Decimal('0')
        return Decimal('0')
    if line.required_downpayment is None:
        return Decimal('0')
    return line.required_downpayment


def sum_booking_required_downpayment(booking: BookingItem) -> Decimal:
    """Sum package and per-line required downpayments on the booking."""
    lines = booking.lines.select_related('company', 'tier', 'package_version')
    total = Decimal('0')
    for line in lines:
        total += _line_required_downpayment(line)
    return total


def validate_field_value_downpayment(field_value: dict) -> None:
    """Raise ``ValidationError`` when downpayment exceeds the line amount."""
    from rest_framework.exceptions import ValidationError

    field_type = field_value.get('field_type')
    price = field_value.get('price')
    if field_type == 'supplier':
        company_id = field_value.get('company_id')
        tier_id = field_value.get('tier_id')
        if company_id is None or tier_id is None:
            return
        package_version_id = field_value.get('package_version_id')
        down = package_required_downpayment_amount(
            int(company_id),
            int(tier_id),
            int(package_version_id) if package_version_id is not None else None,
        )
        if down <= 0:
            return
        if price in (None, ''):
            raise ValidationError(
                {'required_downpayment': 'Set a field amount before entering a downpayment.'},
            )
        price_dec = Decimal(str(price))
        if down > price_dec:
            raise ValidationError(
                {
                    'required_downpayment': (
                        'Downpayment cannot exceed the field amount.'
                    ),
                },
            )
        return

    raw = field_value.get('required_downpayment')
    if raw in (None, ''):
        return
    down = Decimal(str(raw))
    if price in (None, ''):
        raise ValidationError(
            {'required_downpayment': 'Set a field amount before entering a downpayment.'},
        )
    price_dec = Decimal(str(price))
    if down > price_dec:
        raise ValidationError(
            {
                'required_downpayment': (
                    'Downpayment cannot exceed the field amount.'
                ),
            },
        )


def sum_booking_required_downpayment_from_field_dicts(
    field_values_data: list[dict],
) -> Decimal:
    """Estimate downpayment from unsaved line payloads (create/update before lines exist)."""
    total = Decimal('0')
    for fv in field_values_data:
        if fv.get('field_type') == 'supplier':
            company_id = fv.get('company_id')
            tier_id = fv.get('tier_id')
            if company_id is None or tier_id is None:
                continue
            package_version_id = fv.get('package_version_id')
            total += package_required_downpayment_amount(
                int(company_id),
                int(tier_id),
                int(package_version_id) if package_version_id is not None else None,
            )
            continue
        raw = fv.get('required_downpayment')
        if raw in (None, ''):
            continue
        total += Decimal(str(raw))
    return total
