"""Daily booking capacity checks per supplier company."""

from __future__ import annotations

from datetime import date

from django.db.models import Exists, OuterRef

from companies.models import Company

from .models import Quotation
from .payment_validity import valid_booking_payments_queryset


def count_supplier_bookings_on_date(
    account_id: int,
    supplier_company_id: int,
    event_date: date,
    *,
    exclude_quotation_id: int | None = None,
) -> int:
    """
    Distinct bookings on ``event_date`` with a supplier line for ``supplier_company_id``
    and at least one valid payment on ``booking_payments``.
    """
    valid_payment = valid_booking_payments_queryset().filter(
        quotation_id=OuterRef('pk'),
    )
    qs = (
        Quotation.objects.filter(
            account_id=account_id,
            date_of_event__date=event_date,
            lines__company_id=supplier_company_id,
        )
        .annotate(_has_valid_payment=Exists(valid_payment))
        .filter(_has_valid_payment=True)
        .distinct()
    )
    if exclude_quotation_id is not None:
        qs = qs.exclude(pk=exclude_quotation_id)
    return qs.count()


def supplier_booking_capacity_status(
    account_id: int,
    supplier_company_id: int,
    event_date: date,
    *,
    exclude_quotation_id: int | None = None,
) -> dict:
    company = Company.objects.filter(
        pk=supplier_company_id,
        deleted_at__isnull=True,
    ).first()
    if company is None:
        return {
            'supplier_id': supplier_company_id,
            'max_bookings_per_day': 1,
            'booking_count': 0,
            'at_capacity': False,
            'available': True,
            'requires_valid_payment': True,
        }

    max_allowed = company.max_bookings_per_day
    booking_count = count_supplier_bookings_on_date(
        account_id,
        supplier_company_id,
        event_date,
        exclude_quotation_id=exclude_quotation_id,
    )
    at_capacity = booking_count >= max_allowed
    return {
        'supplier_id': supplier_company_id,
        'max_bookings_per_day': max_allowed,
        'booking_count': booking_count,
        'at_capacity': at_capacity,
        'available': not at_capacity,
        'requires_valid_payment': True,
    }
