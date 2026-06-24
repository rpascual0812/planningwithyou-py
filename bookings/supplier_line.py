"""Supplier booking lines: package, supplier company, and package version FKs."""

from __future__ import annotations

import json
from typing import Any

from packages.models import PackagePrice

from .models import QuotationLine


def parse_supplier_field_value(raw: str) -> dict[str, Any]:
    if not (raw or '').strip():
        return {'package_id': None, 'supplier_id': None, 'price': None}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {'package_id': None, 'supplier_id': None, 'price': None}
    if not isinstance(data, dict):
        return {'package_id': None, 'supplier_id': None, 'price': None}

    def _int_or_none(key: str):
        val = data.get(key)
        if val is None or val == '':
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    price_raw = data.get('price')
    price = None if price_raw in (None, '') else str(price_raw)
    package_id = _int_or_none('package_id')
    if package_id is None:
        package_id = _int_or_none('tier_id')
    return {
        'package_id': package_id,
        'supplier_id': _int_or_none('supplier_id'),
        'price': price,
    }


def _coerce_int(value: Any) -> int | None:
    if value is None or value == '':
        return None
    if hasattr(value, 'pk'):
        return int(value.pk)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def supplier_ids_from_field_dict(field_value: dict) -> tuple[int | None, int | None]:
    package_id = _coerce_int(
        field_value.get('package_id')
        or field_value.get('tier_id')
        or field_value.get('package'),
    )
    company_id = _coerce_int(
        field_value.get('company_id') or field_value.get('company'),
    )
    raw = field_value.get('value') or ''
    if str(raw).strip():
        parsed = parse_supplier_field_value(str(raw))
        package_id = package_id or parsed.get('package_id')
        company_id = company_id or parsed.get('supplier_id')
    return package_id, company_id


def _extract_supplier_price_from_value(field_value: dict) -> None:
    raw = field_value.get('value') or ''
    if not str(raw).strip():
        return
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(data, dict):
        return
    json_price = data.pop('price', None)
    if field_value.get('price') in (None, '') and json_price not in (None, ''):
        field_value['price'] = json_price


def prepare_supplier_field_dict(
    field_value: dict,
    *,
    tenant_account_id: int | None = None,
) -> None:
    """Persist supplier selection on FK columns; keep ``value`` empty."""
    if field_value.get('field_type') != 'supplier':
        return
    _extract_supplier_price_from_value(field_value)
    package_id, company_id = supplier_ids_from_field_dict(field_value)
    package_version_id = _coerce_int(field_value.get('package_version_id'))
    for key in ('package', 'tier', 'company', 'package_version'):
        field_value.pop(key, None)
    if package_id is not None and company_id is not None:
        package_price = _package_query_for_supplier_line(
            company_id,
            package_id,
            package_version_id,
        )
        if package_price is None:
            from users.supplier_price import resolve_active_package_for_supplier_package

            package_price = resolve_active_package_for_supplier_package(
                company_id,
                package_id,
            )
        field_value['company_id'] = company_id
        field_value['package_id'] = package_id
        field_value['package_version_id'] = (
            package_price.package_version_id if package_price is not None else None
        )
        if field_value.get('price') in (None, '') and tenant_account_id is not None:
            from users.supplier_price import resolve_supplier_package_booking_price

            resolved = resolve_supplier_package_booking_price(
                company_id,
                package_id,
                tenant_account_id,
            )
            if resolved is not None:
                field_value['price'] = resolved
            elif package_price is not None:
                field_value['price'] = package_price.total_price
    else:
        field_value['company_id'] = None
        field_value['package_id'] = None
        field_value['package_version_id'] = None
    field_value['value'] = ''


def supplier_selection_from_line(line: QuotationLine) -> dict[str, Any]:
    if line.field_type != 'supplier':
        return {'package_id': None, 'supplier_id': None, 'price': None}
    if line.company_id and line.package_id:
        price = None if line.price is None else str(line.price)
        return {
            'package_id': line.package_id,
            'supplier_id': line.company_id,
            'price': price,
        }
    return parse_supplier_field_value(line.value or '')


def supplier_value_json_for_line(line: QuotationLine) -> str:
    parsed = supplier_selection_from_line(line)
    package_id = parsed.get('package_id')
    supplier_id = parsed.get('supplier_id')
    if package_id is None and supplier_id is None:
        return ''
    return json.dumps({'package_id': package_id, 'supplier_id': supplier_id})


def _package_query_for_supplier_line(
    company_id: int,
    package_id: int,
    package_version_id: int | None = None,
) -> PackagePrice | None:
    """Match ``package_prices`` row for supplier company + package (+ optional version)."""
    qs = PackagePrice.objects.filter(
        company_id=company_id,
        package_id=package_id,
        deleted_at__isnull=True,
    )
    if package_version_id is not None:
        package_price = qs.filter(package_version_id=package_version_id).first()
        if package_price is not None:
            return package_price
        # Support rows where ``package_version_id`` was stored as ``package_prices.id``.
        return qs.filter(pk=package_version_id).first()
    return qs.order_by('-is_active', '-id').first()


def package_for_supplier_booking_line(line: QuotationLine) -> PackagePrice | None:
    """
    Package price row for a supplier booking line using stored FK columns.

    Uses ``quotation_lines.company_id``, ``package_id``, and ``package_version_id``.
    Falls back to legacy JSON value + current version resolution when FKs are missing.
    """
    if line.field_type != 'supplier':
        return None
    if line.company_id and line.package_id:
        package_price = _package_query_for_supplier_line(
            line.company_id,
            line.package_id,
            line.package_version_id,
        )
        if package_price is not None:
            return package_price
    parsed = supplier_selection_from_line(line)
    company_id = parsed.get('supplier_id')
    package_id = parsed.get('package_id')
    if company_id is None or package_id is None:
        return None
    from users.supplier_price import resolve_active_package_for_supplier_package

    return resolve_active_package_for_supplier_package(int(company_id), int(package_id))
