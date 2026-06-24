import re
from decimal import Decimal, InvalidOperation

from .models import QuotationLine
from .supplier_line import parse_supplier_field_value, supplier_selection_from_line

CLIENT_GROUP_RE = re.compile(r'client|customer|contact', re.IGNORECASE)


def _parse_amount(raw) -> Decimal | None:
    if raw is None or raw == '':
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _configured_line_price(line: QuotationLine) -> Decimal | None:
    if line.price is None:
        return None
    return line.price


def resolve_booking_line_price(line: QuotationLine) -> Decimal | None:
    if not (line.label or '').strip():
        return None

    if line.field_type == 'select':
        if (line.value or '').strip():
            for opt in line.options or []:
                if isinstance(opt, dict) and opt.get('label') == line.value:
                    raw = opt.get('price')
                    if raw in (None, ''):
                        raw = line.price
                    return _parse_amount(raw)
        return _configured_line_price(line)

    if line.field_type == 'supplier':
        parsed = supplier_selection_from_line(line)
        if parsed['package_id'] is None or parsed['supplier_id'] is None:
            return None
        raw = line.price if line.price is not None else parsed.get('price')
        amount = _parse_amount(raw)
        if amount is not None:
            return amount
        from .supplier_line import package_for_supplier_booking_line

        package = package_for_supplier_booking_line(line)
        if package is not None:
            return package.total_price
        return None

    if line.field_type == 'checkbox':
        if line.value != 'true':
            return None
        return _configured_line_price(line)

    return _configured_line_price(line)


def is_client_group_name(name: str) -> bool:
    return bool(CLIENT_GROUP_RE.search(name or ''))


def client_detail_lines(lines) -> list[QuotationLine]:
    """Lines in client/customer/contact groups, excluding supplier fields."""
    result = []
    for line in lines:
        group_name = line.quotation_group.name if line.quotation_group_id else ''
        if not is_client_group_name(group_name):
            continue
        if line.field_type == 'supplier':
            continue
        result.append(line)
    return result
