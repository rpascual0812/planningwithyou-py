from decimal import Decimal, InvalidOperation

from suppliers.models import SupplierSetting, SupplierSettingTier, Tier


def supplier_accounts_with_price_queryset(qs, tenant_account_id):
    """Annotate supplier accounts with tier + price from supplier_setting_tiers."""
    from django.db.models import OuterRef, Subquery

    tier_row_sq = SupplierSettingTier.objects.filter(
        supplier_setting__supplier_id=OuterRef('pk'),
        supplier_setting__account_id=tenant_account_id,
    ).order_by('-updated_at', 'tier__name')

    return qs.annotate(
        price=Subquery(tier_row_sq.values('price')[:1]),
        tier_id=Subquery(tier_row_sq.values('tier_id')[:1]),
    )


def parse_price_value(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def set_supplier_tier_pricing(
    supplier_account_id,
    tenant_account_id,
    *,
    tier_id=None,
    price=None,
    price_unset=False,
):
    """
    Persist tier selection and/or price on supplier_setting_tiers for this tenant.

    ``price_unset`` is True when ``price`` was not included in the API payload.
    """
    setting, _ = SupplierSetting.objects.get_or_create(
        supplier_id=supplier_account_id,
        account_id=tenant_account_id,
        defaults={'is_active': True},
    )

    tier_row = None
    if tier_id is not None:
        tier = Tier.objects.filter(
            pk=tier_id,
            account_id=tenant_account_id,
            is_active=True,
            deleted_at__isnull=True,
        ).first()
        if tier is None:
            return
        tier_row, _ = SupplierSettingTier.objects.get_or_create(
            supplier_setting=setting,
            tier=tier,
        )
    else:
        tier_row = (
            SupplierSettingTier.objects.filter(supplier_setting=setting)
            .order_by('-updated_at', 'tier__name')
            .first()
        )

    if tier_row is None:
        default_tier = Tier.objects.filter(
            account_id=tenant_account_id,
            is_active=True,
            deleted_at__isnull=True,
        ).order_by('name').first()
        if default_tier is None:
            return
        tier_row, _ = SupplierSettingTier.objects.get_or_create(
            supplier_setting=setting,
            tier=default_tier,
        )

    update_fields = ['updated_at']
    if not price_unset:
        tier_row.price = price
        update_fields.append('price')
    tier_row.save(update_fields=update_fields)


def set_supplier_account_price(supplier_account_id, tenant_account_id, price):
    """Persist price on the active tier row for this supplier setting."""
    set_supplier_tier_pricing(
        supplier_account_id,
        tenant_account_id,
        price=price,
    )


def _decimal_to_api(value):
    if value is None:
        return None
    return format(value, 'f').rstrip('0').rstrip('.') or '0'


def get_supplier_account_tier_pricing(supplier_account_id, tenant_account_id):
    """All active tiers for the tenant with pricing from supplier_setting_tiers."""
    tiers = Tier.objects.filter(
        account_id=tenant_account_id,
        is_active=True,
        deleted_at__isnull=True,
    ).order_by('name')

    setting = SupplierSetting.objects.filter(
        supplier_id=supplier_account_id,
        account_id=tenant_account_id,
    ).first()

    existing = {}
    if setting:
        for row in SupplierSettingTier.objects.filter(supplier_setting=setting):
            existing[row.tier_id] = row

    return [
        {
            'tier_id': tier.id,
            'tier_name': tier.name,
            'discount': _decimal_to_api(existing[tier.id].discount)
            if tier.id in existing
            else None,
            'mark_up': _decimal_to_api(existing[tier.id].mark_up)
            if tier.id in existing
            else None,
            'price': _decimal_to_api(existing[tier.id].price)
            if tier.id in existing
            else None,
        }
        for tier in tiers
    ]


def build_supplier_tiers_by_account(supplier_account_ids, tenant_account_id):
    """Tier pricing rows keyed by supplier account id (for list views)."""
    if not supplier_account_ids:
        return {}

    tier_rows = list(
        Tier.objects.filter(
            account_id=tenant_account_id,
            is_active=True,
            deleted_at__isnull=True,
        ).order_by('name').values_list('id', 'name'),
    )

    settings = SupplierSetting.objects.filter(
        supplier_id__in=supplier_account_ids,
        account_id=tenant_account_id,
    ).prefetch_related('tiers')

    existing_by_supplier = {}
    for setting in settings:
        existing_by_supplier[setting.supplier_id] = {
            row.tier_id: row for row in setting.tiers.all()
        }

    result = {}
    for supplier_id in supplier_account_ids:
        existing = existing_by_supplier.get(supplier_id, {})
        result[supplier_id] = [
            {
                'tier_id': tier_id,
                'tier_name': tier_name,
                'discount': _decimal_to_api(existing[tier_id].discount)
                if tier_id in existing
                else None,
                'mark_up': _decimal_to_api(existing[tier_id].mark_up)
                if tier_id in existing
                else None,
                'price': _decimal_to_api(existing[tier_id].price)
                if tier_id in existing
                else None,
            }
            for tier_id, tier_name in tier_rows
        ]
    return result


def save_supplier_account_tier_pricing(
    supplier_account_id,
    tenant_account_id,
    tiers_data,
):
    """Persist discount, mark-up, and price for each tier row."""
    setting, _ = SupplierSetting.objects.get_or_create(
        supplier_id=supplier_account_id,
        account_id=tenant_account_id,
        defaults={'is_active': True},
    )

    valid_tier_ids = set(
        Tier.objects.filter(
            account_id=tenant_account_id,
            is_active=True,
            deleted_at__isnull=True,
        ).values_list('id', flat=True),
    )

    for item in tiers_data:
        tier_id = item.get('tier_id')
        if tier_id not in valid_tier_ids:
            continue
        tier_row, _ = SupplierSettingTier.objects.get_or_create(
            supplier_setting=setting,
            tier_id=tier_id,
        )
        tier_row.discount = parse_price_value(item.get('discount'))
        tier_row.mark_up = parse_price_value(item.get('mark_up'))
        tier_row.price = parse_price_value(item.get('price'))
        tier_row.save(
            update_fields=['discount', 'mark_up', 'price', 'updated_at'],
        )
