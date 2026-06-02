"""Aggregate booking, payment, and calendar metrics per company for the dashboard."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from calendars.models import Calendar
from companies.models import Company

from .models import BookingItem, BookingPayment, BookingStatus, Tag
from .payment_breakdown import (
    TWOPLACES,
    _booking_credit_amount_field,
    booking_remaining_balance,
)
from .payment_validity import valid_booking_payments_queryset

_FAILED_PAYMENT_STATUSES = frozenset({
    'failed',
    'cancelled',
    'canceled',
    'void',
    'refunded',
})
_UPCOMING_LIMIT = 6
_PROJECT_LIST_LIMIT = 6


def _decimal_str(value: Decimal | None) -> str:
    if value is None:
        return '0.00'
    return str(value.quantize(TWOPLACES))


def _sum_booking_financials(booking_ids: list[int]) -> dict:
    if not booking_ids:
        zero = _decimal_str(Decimal('0'))
        return {
            'total_amount': zero,
            'paid_amount': zero,
            'remaining_amount': zero,
            'downpayment_required': zero,
            'outstanding_booking_count': 0,
            'downpayment_due_count': 0,
        }

    bookings = list(
        BookingItem.objects.filter(pk__in=booking_ids).only(
            'id',
            'total_amount',
            'required_downpayment_amount',
        ),
    )
    total_booked = Decimal('0')
    downpayment_required = Decimal('0')
    paid_total = Decimal('0')
    remaining_total = Decimal('0')
    outstanding_count = 0
    downpayment_due_count = 0

    credit = _booking_credit_amount_field()
    paid_by_booking = {
        row['booking_id']: row['paid'] or Decimal('0')
        for row in valid_booking_payments_queryset()
        .filter(booking_id__in=booking_ids)
        .values('booking_id')
        .annotate(paid=Sum(credit))
    }

    for booking in bookings:
        total = booking.total_amount or Decimal('0')
        total_booked += total
        downpayment_required += booking.required_downpayment_amount or Decimal('0')
        paid = paid_by_booking.get(booking.pk, Decimal('0'))
        paid_total += paid
        remaining = booking_remaining_balance(booking)
        remaining_total += remaining
        if remaining > Decimal('0'):
            outstanding_count += 1
        required = booking.required_downpayment_amount or Decimal('0')
        if required > Decimal('0') and paid < required:
            downpayment_due_count += 1

    return {
        'total_amount': _decimal_str(total_booked),
        'paid_amount': _decimal_str(paid_total),
        'remaining_amount': _decimal_str(remaining_total),
        'downpayment_required': _decimal_str(downpayment_required),
        'outstanding_booking_count': outstanding_count,
        'downpayment_due_count': downpayment_due_count,
    }


def _bookings_by_status(
    booking_ids: list[int],
    account_id: int,
    company_id: int,
) -> list[dict]:
    if not booking_ids:
        return []
    counts = {
        row['status_id']: row['count']
        for row in BookingItem.objects.filter(pk__in=booking_ids)
        .values('status_id')
        .annotate(count=Count('id'))
    }
    statuses = BookingStatus.objects.filter(
        account_id=account_id,
        company_id=company_id,
    ).order_by('sort_order', 'id')
    return [
        {
            'status_id': status.id,
            'title': status.title,
            'color': status.color,
            'count': counts.get(status.id, 0),
        }
        for status in statuses
        if counts.get(status.id, 0) > 0
    ]


def _upcoming_bookings(qs, *, limit: int = _UPCOMING_LIMIT) -> list[dict]:
    now = timezone.now()
    rows = (
        qs.filter(date_of_event__gte=now)
        .order_by('date_of_event', 'id')
        .values('id', 'unique_id', 'title', 'date_of_event')[:limit]
    )
    return [
        {
            'id': row['id'],
            'unique_id': row['unique_id'],
            'title': row['title'],
            'date_of_event': (
                row['date_of_event'].isoformat() if row['date_of_event'] else None
            ),
        }
        for row in rows
    ]


def _payout_summary(company_id: int, account_id: int) -> dict:
    base_qs = valid_booking_payments_queryset().filter(
        account_id=account_id,
        company_id=company_id,
    )
    credit = _booking_credit_amount_field()
    pending = base_qs.filter(payout_sent_at__isnull=True).aggregate(
        count=Count('id'),
        amount=Sum(credit),
    )
    sent = base_qs.filter(payout_sent_at__isnull=False).aggregate(
        count=Count('id'),
        amount=Sum(credit),
    )
    return {
        'pending_count': pending['count'] or 0,
        'pending_amount': _decimal_str(pending['amount']),
        'sent_count': sent['count'] or 0,
        'sent_amount': _decimal_str(sent['amount']),
    }


def _failed_payment_count(company_id: int, account_id: int) -> int:
    return BookingPayment.objects.filter(
        account_id=account_id,
        company_id=company_id,
        deleted_at__isnull=True,
        transaction_status__in=list(_FAILED_PAYMENT_STATUSES),
    ).count()


def _calendar_summary(company_id: int, account_id: int, *, now, week_end) -> dict:
    base = Calendar.objects.filter(
        account_id=account_id,
        company_id=company_id,
        deleted_at__isnull=True,
    )
    return {
        'events_this_week': base.filter(start__gte=now, start__lt=week_end).count(),
        'upcoming_count': base.filter(start__gte=now).count(),
    }


def _resolve_dashboard_tag_id(
    account_id: int,
    company_id: int,
    configured_value: str,
) -> int | None:
    tags_qs = Tag.objects.filter(account_id=account_id, company_id=company_id)
    if configured_value:
        try:
            tag_id = int(configured_value)
        except (TypeError, ValueError):
            tag_id = None
        if tag_id is not None and tags_qs.filter(pk=tag_id).exists():
            return tag_id
    for fallback_name in ('done', 'completed'):
        tag_id = (
            tags_qs.filter(tag__iexact=fallback_name)
            .order_by('id')
            .values_list('pk', flat=True)
            .first()
        )
        if tag_id is not None:
            return tag_id
    return (
        tags_qs.order_by('tag', 'id')
        .values_list('pk', flat=True)
        .first()
    )


def profit_progress_total_for_tag(
    account_id: int,
    company_id: int,
    tag_id: int | None,
) -> Decimal:
    if tag_id is None:
        return Decimal('0')
    status_ids = BookingStatus.objects.filter(
        account_id=account_id,
        company_id=company_id,
        tags__id=tag_id,
    ).values_list('pk', flat=True)
    if not status_ids:
        return Decimal('0')
    total = BookingItem.objects.filter(
        account_id=account_id,
        company_id=company_id,
        status_id__in=status_ids,
    ).aggregate(sum_total=Sum('total_amount'))['sum_total']
    return total or Decimal('0')


def format_profit_progress_display(total: Decimal) -> str:
    amount = total if total is not None else Decimal('0')
    if amount < 0:
        amount = Decimal('0')
    if amount >= Decimal('1000000'):
        scaled = amount / Decimal('1000000')
        return f'{scaled.quantize(Decimal("0.1"))}M+'
    if amount >= Decimal('1000'):
        scaled = amount / Decimal('1000')
        return f'{scaled.quantize(Decimal("0.1"))}K+'
    return f'{amount.quantize(TWOPLACES)}+'


def _resolve_profit_progress_tag_id(
    account_id: int,
    company_id: int,
    configured_value: str,
) -> int | None:
    return _resolve_dashboard_tag_id(account_id, company_id, configured_value)


def active_projects_count_for_tag(
    account_id: int,
    company_id: int,
    tag_id: int | None,
) -> int:
    if tag_id is None:
        return 0
    status_ids = BookingStatus.objects.filter(
        account_id=account_id,
        company_id=company_id,
        tags__id=tag_id,
    ).values_list('pk', flat=True)
    if not status_ids:
        return 0
    return BookingItem.objects.filter(
        account_id=account_id,
        company_id=company_id,
        status_id__in=status_ids,
    ).count()


def format_active_projects_display(count: int) -> str:
    if count < 0:
        count = 0
    return str(count)


def build_active_projects_for_company(
    account_id: int,
    company_id: int,
    configured_tag_value: str,
) -> dict:
    tag_id = _resolve_dashboard_tag_id(
        account_id,
        company_id,
        configured_tag_value,
    )
    tag_name = ''
    if tag_id is not None:
        tag_name = (
            Tag.objects.filter(
                pk=tag_id,
                account_id=account_id,
                company_id=company_id,
            )
            .values_list('tag', flat=True)
            .first()
            or ''
        )
    count = active_projects_count_for_tag(account_id, company_id, tag_id)
    return {
        'company_id': company_id,
        'tag_id': tag_id,
        'tag_name': tag_name,
        'count': count,
        'display_value': format_active_projects_display(count),
    }


def build_profit_progress_for_company(
    account_id: int,
    company_id: int,
    configured_tag_value: str,
) -> dict:
    tag_id = _resolve_dashboard_tag_id(
        account_id,
        company_id,
        configured_tag_value,
    )
    tag_name = ''
    if tag_id is not None:
        tag_name = (
            Tag.objects.filter(
                pk=tag_id,
                account_id=account_id,
                company_id=company_id,
            )
            .values_list('tag', flat=True)
            .first()
            or ''
        )
    total = profit_progress_total_for_tag(account_id, company_id, tag_id)
    return {
        'company_id': company_id,
        'tag_id': tag_id,
        'tag_name': tag_name,
        'total_amount': _decimal_str(total),
        'display_value': format_profit_progress_display(total),
    }


def build_dashboard_for_account(
    account_id: int,
    *,
    user_company_id: int | None = None,
) -> dict:
    now = timezone.now()
    week_end = now + timedelta(days=7)
    companies = list(
        Company.objects.filter(
            account_id=account_id,
            deleted_at__isnull=True,
            is_active=True,
        ).order_by('-is_main', 'sort_order', 'name')
    )
    company_payloads = []
    for company in companies:
        owned_qs = BookingItem.objects.filter(
            account_id=account_id,
            company_id=company.id,
        )
        owned_ids = list(owned_qs.values_list('id', flat=True))
        supplier_qs = (
            BookingItem.objects.filter(
                account_id=account_id,
                lines__company_id=company.id,
            )
            .exclude(company_id=company.id)
            .distinct()
        )
        supplier_ids = list(supplier_qs.values_list('id', flat=True))
        company_payloads.append({
            'id': company.id,
            'name': company.name,
            'is_main': company.is_main,
            'kyb_verified': company.kyb_verified,
            'is_user_company': company.id == user_company_id,
            'bookings_owned': {
                'count': len(owned_ids),
                'by_status': _bookings_by_status(
                    owned_ids,
                    account_id,
                    company.id,
                ),
                **_sum_booking_financials(owned_ids),
                'upcoming': _upcoming_bookings(owned_qs),
            },
            'bookings_as_supplier': {
                'count': len(supplier_ids),
                'upcoming': _upcoming_bookings(supplier_qs),
            },
            'payouts': _payout_summary(company.id, account_id),
            'calendar': _calendar_summary(
                company.id,
                account_id,
                now=now,
                week_end=week_end,
            ),
            'failed_payment_count': _failed_payment_count(company.id, account_id),
        })
    return {
        'generated_at': now.isoformat(),
        'companies': company_payloads,
    }
