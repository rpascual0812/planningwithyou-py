"""Board view queryset helpers for paginated kanban columns."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import (
    Case,
    DecimalField,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
    When,
)
from django.db.models.functions import Coalesce

from .models import BookingStatus
from .payment_validity import valid_booking_payments_queryset

TWOPLACES = Decimal('0.01')


def booking_list_board_view_requested(request) -> bool:
    return request.query_params.get('view', '').strip().lower() == 'board'


def annotate_booking_board_payments(queryset: QuerySet) -> QuerySet:
    """Annotate ``_paid_amount`` to avoid per-row payment queries on board lists."""
    credit = Case(
        When(base_amount__gt=0, then=F('base_amount')),
        default=F('amount'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    paid_subq = (
        valid_booking_payments_queryset()
        .filter(booking_id=OuterRef('pk'))
        .values('booking_id')
        .annotate(total=Sum(credit))
        .values('total')[:1]
    )
    return queryset.annotate(
        _paid_amount=Coalesce(
            Subquery(paid_subq),
            Decimal('0'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )


def _local_status_ids(
    account_id: int,
    company_id: int | None = None,
) -> list[int]:
    qs = BookingStatus.objects.filter(account_id=account_id)
    if company_id is not None:
        qs = qs.filter(company_id=company_id)
    return list(qs.values_list('id', flat=True))


def _title_match_q(column_title: str) -> Q:
    title = column_title.strip()
    if not title:
        return Q(pk__in=[])
    return Q(status__title__iexact=title)


def filter_booking_items_board_column(
    queryset: QuerySet,
    column_id: int,
    account_id: int,
    company_id: int | None = None,
) -> QuerySet:
    """
    Items shown in a kanban column:

    - Bookings whose ``status_id`` is the column's status, or
    - Cross-company bookings whose status title matches the column title
      when their status id is not one of this account's column ids.
    """
    status_qs = BookingStatus.objects.filter(pk=column_id, account_id=account_id)
    if company_id is not None:
        status_qs = status_qs.filter(company_id=company_id)
    status = status_qs.first()
    if status is None:
        return queryset.none()

    local_ids = _local_status_ids(account_id, company_id)
    title_q = _title_match_q(status.title)
    return queryset.filter(Q(status_id=column_id) | (~Q(status_id__in=local_ids) & title_q))


def filter_booking_items_board_foreign_slot(
    queryset: QuerySet,
    account_id: int,
    user_company_id: int | None,
) -> QuerySet:
    """
    Other-company bookings whose status does not map to any local column
    (by id or title).
    """
    if user_company_id is None:
        return queryset.none()

    status_qs = BookingStatus.objects.filter(account_id=account_id)
    if user_company_id is not None:
        status_qs = status_qs.filter(company_id=user_company_id)
    local_statuses = list(status_qs.values('id', 'title'))
    local_ids = [row['id'] for row in local_statuses]

    matched = Q(status_id__in=local_ids)
    for row in local_statuses:
        matched |= _title_match_q(row['title'])

    return queryset.filter(~Q(company_id=user_company_id)).exclude(matched)
