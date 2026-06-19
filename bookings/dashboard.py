"""Aggregate booking, payment, and calendar metrics per company for the dashboard."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from calendars.models import Calendar
from companies.models import Company

from .models import Quotation, QuotationPayment, QuotationStatus, Tag
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


def _sum_booking_financials(quotation_ids: list[int]) -> dict:
    if not quotation_ids:
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
        Quotation.objects.filter(pk__in=quotation_ids).only(
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
        row['quotation_id']: row['paid'] or Decimal('0')
        for row in valid_booking_payments_queryset()
        .filter(quotation_id__in=quotation_ids)
        .values('quotation_id')
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
    quotation_ids: list[int],
    account_id: int,
    company_id: int,
) -> list[dict]:
    if not quotation_ids:
        return []
    counts = {
        row['status_id']: row['count']
        for row in Quotation.objects.filter(pk__in=quotation_ids)
        .values('status_id')
        .annotate(count=Count('id'))
    }
    statuses = QuotationStatus.objects.filter(
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
    return QuotationPayment.objects.filter(
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


def parse_configured_tag_ids(configured_value: str) -> list[int]:
    ids: list[int] = []
    for part in configured_value.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except (TypeError, ValueError):
            continue
    return ids


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


def resolve_dashboard_tag_ids(
    account_id: int,
    company_id: int,
    configured_value: str,
    *,
    has_saved_config: bool,
) -> list[int]:
    tags_qs = Tag.objects.filter(account_id=account_id, company_id=company_id)
    if has_saved_config:
        parsed = parse_configured_tag_ids(configured_value)
        valid_ids = set(tags_qs.filter(pk__in=parsed).values_list('pk', flat=True))
        return [tag_id for tag_id in parsed if tag_id in valid_ids]
    tag_id = _resolve_dashboard_tag_id(account_id, company_id, configured_value)
    return [tag_id] if tag_id is not None else []


def _tag_names_for_ids(
    account_id: int,
    company_id: int,
    tag_ids: list[int],
) -> list[str]:
    if not tag_ids:
        return []
    by_id = {
        row['pk']: row['tag']
        for row in Tag.objects.filter(
            pk__in=tag_ids,
            account_id=account_id,
            company_id=company_id,
        ).values('pk', 'tag')
    }
    return [by_id[tag_id] for tag_id in tag_ids if tag_id in by_id]


def profit_progress_total_for_tags(
    account_id: int,
    company_id: int,
    tag_ids: list[int],
) -> Decimal:
    if not tag_ids:
        return Decimal('0')
    status_ids = QuotationStatus.objects.filter(
        account_id=account_id,
        company_id=company_id,
        tags__id__in=tag_ids,
    ).distinct().values_list('pk', flat=True)
    if not status_ids:
        return Decimal('0')
    total = Quotation.objects.filter(
        account_id=account_id,
        company_id=company_id,
        status_id__in=status_ids,
    ).aggregate(sum_total=Sum('total_amount'))['sum_total']
    return total or Decimal('0')


def profit_progress_total_for_tag(
    account_id: int,
    company_id: int,
    tag_id: int | None,
) -> Decimal:
    if tag_id is None:
        return Decimal('0')
    return profit_progress_total_for_tags(account_id, company_id, [tag_id])


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


def active_projects_count_for_tags(
    account_id: int,
    company_id: int,
    tag_ids: list[int],
) -> int:
    if not tag_ids:
        return 0
    status_ids = QuotationStatus.objects.filter(
        account_id=account_id,
        company_id=company_id,
        tags__id__in=tag_ids,
    ).distinct().values_list('pk', flat=True)
    if not status_ids:
        return 0
    return Quotation.objects.filter(
        account_id=account_id,
        company_id=company_id,
        status_id__in=status_ids,
    ).count()


def active_projects_count_for_tag(
    account_id: int,
    company_id: int,
    tag_id: int | None,
) -> int:
    if tag_id is None:
        return 0
    return active_projects_count_for_tags(account_id, company_id, [tag_id])


def format_active_projects_display(count: int) -> str:
    if count < 0:
        count = 0
    return str(count)


def build_active_projects_for_company(
    account_id: int,
    company_id: int,
    configured_tag_value: str,
    *,
    has_saved_config: bool = False,
) -> dict:
    tag_ids = resolve_dashboard_tag_ids(
        account_id,
        company_id,
        configured_tag_value,
        has_saved_config=has_saved_config,
    )
    tag_names = _tag_names_for_ids(account_id, company_id, tag_ids)
    count = active_projects_count_for_tags(account_id, company_id, tag_ids)
    return {
        'company_id': company_id,
        'tag_id': tag_ids[0] if tag_ids else None,
        'tag_ids': tag_ids,
        'tag_name': ', '.join(tag_names),
        'count': count,
        'display_value': format_active_projects_display(count),
    }


def build_profit_progress_for_company(
    account_id: int,
    company_id: int,
    configured_tag_value: str,
    *,
    has_saved_config: bool = False,
) -> dict:
    tag_ids = resolve_dashboard_tag_ids(
        account_id,
        company_id,
        configured_tag_value,
        has_saved_config=has_saved_config,
    )
    tag_names = _tag_names_for_ids(account_id, company_id, tag_ids)
    total = profit_progress_total_for_tags(account_id, company_id, tag_ids)
    return {
        'company_id': company_id,
        'tag_id': tag_ids[0] if tag_ids else None,
        'tag_ids': tag_ids,
        'tag_name': ', '.join(tag_names),
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
        owned_qs = Quotation.objects.filter(
            account_id=account_id,
            company_id=company.id,
        )
        owned_ids = list(owned_qs.values_list('id', flat=True))
        supplier_qs = (
            Quotation.objects.filter(
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
