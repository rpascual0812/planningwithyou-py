"""Build a compact, tenant-safe quotation context for LLM prompts."""

from __future__ import annotations

from decimal import Decimal

from bookings.models import Quotation
from bookings.payment_breakdown import (
    booking_payments_paid_base_total,
    booking_remaining_balance,
)
from bookings.supplier_line import supplier_value_json_for_line


def _money(value) -> str:
    if value is None:
        return '0.00'
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal('0.01')))
    return str(value)


def build_quotation_ai_context(quotation: Quotation) -> dict:
    quotation = (
        Quotation.objects.filter(pk=quotation.pk)
        .select_related('contact', 'status', 'company', 'company__account__country')
        .prefetch_related(
            'groups',
            'lines__quotation_group',
            'lines__company',
            'lines__tier',
        )
        .first()
    )
    if quotation is None:
        raise Quotation.DoesNotExist

    contact = quotation.contact
    contact_name = ''
    if contact:
        parts = [(contact.first_name or '').strip(), (contact.last_name or '').strip()]
        contact_name = ' '.join(part for part in parts if part).strip()

    groups: dict[str, list[dict]] = {}
    for line in quotation.lines.all().order_by('sort_order', 'id'):
        group_name = (
            line.quotation_group.name
            if line.quotation_group_id
            else 'Suppliers'
        )
        entry = {
            'label': (line.label or '').strip(),
            'field_type': line.field_type,
            'value': line.value,
            'price': _money(line.price),
            'required_downpayment': _money(line.required_downpayment),
            'is_required': line.is_required,
        }
        if line.field_type == 'supplier':
            entry['value'] = supplier_value_json_for_line(line)
            if line.company_id:
                company = getattr(line, 'company', None)
                entry['supplier_name'] = (
                    (company.name or '').strip() if company is not None else ''
                )
        groups.setdefault(group_name, []).append(entry)

    paid = booking_payments_paid_base_total(quotation.pk)
    remaining = booking_remaining_balance(quotation)

    event_date = ''
    if quotation.date_of_event:
        event_date = quotation.date_of_event.isoformat()

    currency = ''
    country = getattr(getattr(quotation.company, 'account', None), 'country', None)
    if country is not None:
        currency = (country.currency_code or country.currency or '').strip()

    return {
        'quotation_id': quotation.pk,
        'unique_id': (quotation.unique_id or '').strip(),
        'title': (quotation.title or '').strip(),
        'status': (quotation.status.title if quotation.status_id else '').strip(),
        'event_date': event_date,
        'contact_name': contact_name,
        'contact_email': (contact.email or '').strip() if contact else '',
        'company_name': (quotation.company.name or '').strip() if quotation.company_id else '',
        'currency': currency,
        'total_amount': _money(quotation.total_amount),
        'required_downpayment_amount': _money(quotation.required_downpayment_amount),
        'paid_amount': _money(paid),
        'remaining_balance': _money(remaining),
        'notes': (quotation.notes or '').strip(),
        'groups': groups,
    }


def format_quotation_context_for_prompt(context: dict) -> str:
    lines = [
        f"Quotation: {context.get('title')} ({context.get('unique_id')})",
        f"Status: {context.get('status')}",
        f"Event date: {context.get('event_date') or 'Not set'}",
        f"Client: {context.get('contact_name') or 'Not assigned'}",
        f"Company: {context.get('company_name')}",
        f"Total: {context.get('currency', '')} {context.get('total_amount')}".strip(),
        f"Paid: {context.get('currency', '')} {context.get('paid_amount')}".strip(),
        f"Remaining: {context.get('currency', '')} {context.get('remaining_balance')}".strip(),
        f"Required downpayment: {context.get('currency', '')} {context.get('required_downpayment_amount')}".strip(),
    ]
    if context.get('notes'):
        lines.append(f"Notes: {context['notes']}")

    lines.append('Line items by group:')
    groups = context.get('groups') or {}
    if not groups:
        lines.append('- (none)')
    else:
        for group_name, items in groups.items():
            lines.append(f"- {group_name}:")
            for item in items:
                label = item.get('label') or 'Field'
                value = item.get('value') or ''
                price = item.get('price')
                detail = f"  • {label}: {value}"
                if price and price != '0.00':
                    detail += f" (price {price})"
                if item.get('supplier_name'):
                    detail += f" — supplier {item['supplier_name']}"
                lines.append(detail)
    return '\n'.join(lines)
