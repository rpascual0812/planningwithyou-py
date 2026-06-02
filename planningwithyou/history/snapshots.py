"""Per-resource snapshots and change builders."""

from __future__ import annotations

from typing import Any

from planningwithyou.history.core import diff_field_map, diff_named_rows, json_value

ACCOUNT_FIELDS = (
    'name', 'is_active', 'contact_person', 'contact_email',
    'contact_mobile_number', 'timezone', 'country_id',
)

COMPANY_FIELDS = (
    'name', 'supplier_type_id', 'timezone', 'contact_person', 'contact_email',
    'phone_number',
    'mobile_number', 'address', 'website', 'is_active', 'is_main',
    'max_bookings_per_day', 'logo',
)

USER_FIELDS = (
    'username', 'email', 'first_name', 'last_name', 'is_active', 'role',
    'company_id',
)

CONTACT_FIELDS = (
    'first_name', 'last_name', 'email', 'company_org_id', 'notes',
)

BOOKING_STATUS_FIELDS = ('title', 'description', 'color', 'sort_order')

EMAIL_TEMPLATE_FIELDS = (
    'name', 'title', 'subject', 'body', 'is_active', 'company_id', 'template_type',
)
FORM_TEMPLATE_FIELDS = (
    'name', 'description', 'is_active', 'is_default', 'company_id',
)

PHONE_FIELDS = ('number', 'label', 'is_default')
ADDRESS_FIELDS = ('label', 'street', 'city', 'state', 'zip_code', 'country', 'is_default')


def snapshot_account(account) -> dict[str, Any]:
    return {field: json_value(getattr(account, field)) for field in ACCOUNT_FIELDS}


def snapshot_company(company) -> dict[str, Any]:
    return {field: json_value(getattr(company, field)) for field in COMPANY_FIELDS}


def snapshot_user(user) -> dict[str, Any]:
    return {field: json_value(getattr(user, field)) for field in USER_FIELDS}


def snapshot_contact_number(row) -> dict[str, Any]:
    return {field: json_value(getattr(row, field)) for field in PHONE_FIELDS}


def snapshot_contact_address(row) -> dict[str, Any]:
    return {field: json_value(getattr(row, field)) for field in ADDRESS_FIELDS}


def snapshot_contact(contact) -> dict[str, Any]:
    data = {field: json_value(getattr(contact, field)) for field in CONTACT_FIELDS}
    data['phone_numbers'] = [
        snapshot_contact_number(n)
        for n in contact.phone_numbers.order_by('id')
    ]
    data['addresses'] = [
        snapshot_contact_address(a)
        for a in contact.addresses.order_by('id')
    ]
    return data


def snapshot_booking_status(status) -> dict[str, Any]:
    return {field: json_value(getattr(status, field)) for field in BOOKING_STATUS_FIELDS}


def snapshot_email_template(template) -> dict[str, Any]:
    return {field: json_value(getattr(template, field)) for field in EMAIL_TEMPLATE_FIELDS}


def snapshot_form_template_option(option) -> dict[str, Any]:
    return {
        'label': json_value(option.label),
        'price': json_value(option.price),
        'sort_order': json_value(option.sort_order),
    }


def snapshot_form_template_field(field) -> dict[str, Any]:
    return {
        'label': json_value(field.label),
        'field_type': json_value(field.field_type),
        'is_required': json_value(field.is_required),
        'price': json_value(field.price),
        'sort_order': json_value(field.sort_order),
        'options': [
            snapshot_form_template_option(o)
            for o in field.options.order_by('id')
        ],
    }


def snapshot_form_template(template) -> dict[str, Any]:
    data = {field: json_value(getattr(template, field)) for field in FORM_TEMPLATE_FIELDS}
    data['template_fields'] = [
        snapshot_form_template_field(f)
        for f in template.fields.order_by('id').prefetch_related('options')
    ]
    return data


def snapshot_supplier_setting(company_id: int, tenant_account_id: int) -> dict[str, Any]:
    from companies.models import Company
    from users.supplier_price import (
        get_supplier_company_tier_pricing,
        supplier_setting_is_active,
    )

    company = Company.objects.filter(pk=company_id).first()
    return {
        'supplier_company_id': company_id,
        'supplier_name': company.name if company else '',
        'is_active': supplier_setting_is_active(company_id, tenant_account_id),
        'tiers': get_supplier_company_tier_pricing(
            company_id,
            tenant_account_id,
            supplier_account_id=company.account_id if company else None,
        ),
    }


def diff_simple(before: dict[str, Any], after: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    field_changes = diff_field_map(before, after, fields)
    return {'fields': field_changes} if field_changes else {}


def diff_contact(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    field_changes = diff_field_map(before, after, CONTACT_FIELDS)
    if field_changes:
        changes['fields'] = field_changes
    phone_changes = diff_named_rows(
        before.get('phone_numbers', []),
        after.get('phone_numbers', []),
        name_key='number',
    )
    if phone_changes['added'] or phone_changes['removed']:
        changes['phone_numbers'] = phone_changes
    address_changes = diff_named_rows(
        before.get('addresses', []),
        after.get('addresses', []),
        name_key='label',
    )
    if address_changes['added'] or address_changes['removed']:
        changes['addresses'] = address_changes
    return changes


def diff_supplier_setting(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    if before.get('is_active') != after.get('is_active'):
        changes['is_active'] = {'old': before.get('is_active'), 'new': after.get('is_active')}
    if before.get('supplier_name') != after.get('supplier_name'):
        changes['supplier_name'] = {
            'old': before.get('supplier_name'),
            'new': after.get('supplier_name'),
        }
    before_tiers = {t['tier_id']: t for t in before.get('tiers', [])}
    after_tiers = {t['tier_id']: t for t in after.get('tiers', [])}
    tier_changes = []
    for tier_id in sorted(set(before_tiers) | set(after_tiers)):
        old_t = before_tiers.get(tier_id)
        new_t = after_tiers.get(tier_id)
        if old_t == new_t:
            continue
        tier_changes.append({'tier_id': tier_id, 'old': old_t, 'new': new_t})
    if tier_changes:
        changes['tiers'] = tier_changes
    return changes


def diff_form_template(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    field_changes = diff_field_map(before, after, FORM_TEMPLATE_FIELDS)
    if field_changes:
        changes['fields'] = field_changes
    template_field_changes = diff_named_rows(
        before.get('template_fields', []),
        after.get('template_fields', []),
        name_key='label',
    )
    if template_field_changes['added'] or template_field_changes['removed']:
        changes['template_fields'] = template_field_changes
    return changes
