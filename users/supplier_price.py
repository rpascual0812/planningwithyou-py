from decimal import Decimal, InvalidOperation

from suppliers.models import SupplierSetting, SupplierSettingTier, Tier


def supplier_companies_with_price_queryset(qs, tenant_account_id):
    """Annotate companies with tier + price from supplier_setting_tiers."""
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


def _tenant_tiers_qs(tenant_company_id):
    return Tier.objects.filter(
        company_id=tenant_company_id,
        is_active=True,
        deleted_at__isnull=True,
    )


def set_supplier_tier_pricing(
    supplier_company_id,
    tenant_account_id,
    tenant_company_id,
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
        supplier_id=supplier_company_id,
        account_id=tenant_account_id,
        defaults={'is_active': True},
    )

    tier_row = None
    if tier_id is not None:
        tier = _tenant_tiers_qs(tenant_company_id).filter(pk=tier_id).first()
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
        default_tier = _tenant_tiers_qs(tenant_company_id).order_by('name').first()
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


def _decimal_to_api(value):
    if value is None:
        return None
    return format(value, 'f').rstrip('0').rstrip('.') or '0'


def get_supplier_company_tier_options(
    supplier_company_id,
    tenant_account_id,
    tenant_company_id,
):
    """Tier catalog for booking supplier field with optional SST pricing."""
    tiers = _tenant_tiers_qs(tenant_company_id).order_by('name')

    setting = SupplierSetting.objects.filter(
        supplier_id=supplier_company_id,
        account_id=tenant_account_id,
    ).first()

    by_tier_id = {}
    if setting:
        for row in SupplierSettingTier.objects.filter(
            supplier_setting=setting,
        ).select_related('tier'):
            by_tier_id[row.tier_id] = row

    default_type = SupplierSettingTier.AdjustmentType.PERCENT
    return [
        {
            'id': tier.id,
            'name': tier.name,
            'is_active': tier.is_active,
            'discount': row.discount if (row := by_tier_id.get(tier.id)) else None,
            'discount_type': row.discount_type if row else default_type,
            'mark_up': row.mark_up if row else None,
            'mark_up_type': row.mark_up_type if row else default_type,
            'price_override': row.price_override if row else None,
            'tax': row.tax if row else None,
            'price': row.price if row else None,
        }
        for tier in tiers
    ]


def get_supplier_company_tier_pricing(
    supplier_company_id,
    tenant_account_id,
    tenant_company_id,
):
    """All active tiers for the tenant company with pricing from supplier_setting_tiers."""
    tiers = _tenant_tiers_qs(tenant_company_id).order_by('name')

    setting = SupplierSetting.objects.filter(
        supplier_id=supplier_company_id,
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


def build_supplier_tiers_by_company(
    supplier_company_ids,
    tenant_account_id,
    tenant_company_id,
):
    """Tier pricing rows keyed by supplier company id (for list views)."""
    if not supplier_company_ids:
        return {}

    tier_rows = list(
        _tenant_tiers_qs(tenant_company_id).order_by('name').values_list('id', 'name'),
    )

    settings = SupplierSetting.objects.filter(
        supplier_id__in=supplier_company_ids,
        account_id=tenant_account_id,
    ).prefetch_related('tiers')

    existing_by_supplier = {}
    for setting in settings:
        existing_by_supplier[setting.supplier_id] = {
            row.tier_id: row for row in setting.tiers.all()
        }

    result = {}
    for supplier_id in supplier_company_ids:
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


def save_supplier_company_tier_pricing(
    supplier_company_id,
    tenant_account_id,
    tenant_company_id,
    tiers_data,
):
    """Persist discount, mark-up, and price for each tier row."""
    setting, _ = SupplierSetting.objects.get_or_create(
        supplier_id=supplier_company_id,
        account_id=tenant_account_id,
        defaults={'is_active': True},
    )

    valid_tier_ids = set(
        _tenant_tiers_qs(tenant_company_id).values_list('id', flat=True),
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
