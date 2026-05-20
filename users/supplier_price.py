from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from packages.models import Package, PackageVersion
from suppliers.models import SupplierSetting, SupplierSettingTier, Tier


def _supplier_company_tiers_qs(supplier_company_id):
    return Tier.objects.filter(
        company_id=supplier_company_id,
        is_active=True,
        deleted_at__isnull=True,
    )


def _current_package_version_for_company(*, company_id, account_id):
    now = timezone.now()
    return (
        PackageVersion.objects.filter(
            company_id=company_id,
            account_id=account_id,
            deleted_at__isnull=True,
            effectivity_date__isnull=False,
            effectivity_date__lte=now,
        )
        .order_by('-effectivity_date', '-id')
        .first()
    )


def _original_prices_by_tier_id(*, company_id, account_id):
    """Active package total_price per tier for the current package version."""
    version = _current_package_version_for_company(
        company_id=company_id,
        account_id=account_id,
    )
    if version is None:
        return {}
    rows = Package.objects.filter(
        company_id=company_id,
        package_version_id=version.id,
        is_active=True,
        deleted_at__isnull=True,
    ).values('tier_id', 'total_price')
    return {row['tier_id']: row['total_price'] for row in rows}


def parse_price_value(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def normalize_adjustment_type(value):
    choices = SupplierSettingTier.AdjustmentType
    if value in (choices.PERCENT, choices.FIXED):
        return value
    return choices.PERCENT


def _adjustment_amount(base, value, adjustment_type):
    if value is None:
        return Decimal('0')
    if adjustment_type == SupplierSettingTier.AdjustmentType.FIXED:
        return value
    return (base * value) / Decimal('100')


def compute_tier_final_price(
    original_price,
    discount,
    discount_type,
    mark_up,
    mark_up_type,
):
    """Apply discount and mark-up against package total_price (original)."""
    if original_price is None:
        return None
    base = Decimal(original_price)
    if discount is None and mark_up is None:
        return base
    total = base
    if discount is not None:
        total -= _adjustment_amount(base, discount, discount_type)
    if mark_up is not None:
        total += _adjustment_amount(base, mark_up, mark_up_type)
    if total < 0:
        total = Decimal('0')
    return total


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
    *,
    supplier_account_id=None,
):
    """
    Active tiers for the supplier company with SST pricing and package original price.
    """
    from companies.models import Company

    if supplier_account_id is None:
        supplier_account_id = (
            Company.objects.filter(pk=supplier_company_id)
            .values_list('account_id', flat=True)
            .first()
        )

    tiers = _supplier_company_tiers_qs(supplier_company_id).order_by('name')
    original_by_tier = (
        _original_prices_by_tier_id(
            company_id=supplier_company_id,
            account_id=supplier_account_id,
        )
        if supplier_account_id is not None
        else {}
    )

    setting = SupplierSetting.objects.filter(
        supplier_id=supplier_company_id,
        account_id=tenant_account_id,
    ).first()

    existing = {}
    if setting:
        for row in SupplierSettingTier.objects.filter(supplier_setting=setting):
            existing[row.tier_id] = row

    default_type = SupplierSettingTier.AdjustmentType.PERCENT
    return [
        {
            'tier_id': tier.id,
            'tier_name': tier.name,
            'discount': _decimal_to_api(existing[tier.id].discount)
            if tier.id in existing
            else None,
            'discount_type': existing[tier.id].discount_type
            if tier.id in existing
            else default_type,
            'mark_up': _decimal_to_api(existing[tier.id].mark_up)
            if tier.id in existing
            else None,
            'mark_up_type': existing[tier.id].mark_up_type
            if tier.id in existing
            else default_type,
            'price': _decimal_to_api(existing[tier.id].price)
            if tier.id in existing
            else None,
            'original_price': _decimal_to_api(original_by_tier.get(tier.id)),
        }
        for tier in tiers
    ]


def supplier_setting_is_active(supplier_company_id, tenant_account_id):
    """Tenant-specific supplier active flag (off when no supplier_settings row)."""
    setting = SupplierSetting.objects.filter(
        supplier_id=supplier_company_id,
        account_id=tenant_account_id,
    ).first()
    return setting.is_active if setting is not None else False


def build_supplier_setting_active_by_company(
    supplier_company_ids,
    tenant_account_id,
):
    """supplier_settings.is_active keyed by supplier company id."""
    if not supplier_company_ids:
        return {}
    active_by_supplier = dict(
        SupplierSetting.objects.filter(
            supplier_id__in=supplier_company_ids,
            account_id=tenant_account_id,
        ).values_list('supplier_id', 'is_active'),
    )
    return {
        supplier_id: active_by_supplier.get(supplier_id, False)
        for supplier_id in supplier_company_ids
    }


@transaction.atomic
def set_supplier_setting_active(
    supplier_company_id,
    tenant_account_id,
    is_active,
):
    """Upsert supplier_settings and supplier_setting_tiers for all supplier tiers."""
    setting, _ = SupplierSetting.objects.get_or_create(
        supplier_id=supplier_company_id,
        account_id=tenant_account_id,
        defaults={'is_active': is_active},
    )
    setting.is_active = is_active
    setting.save(update_fields=['is_active', 'updated_at'])

    for tier in _supplier_company_tiers_qs(supplier_company_id):
        SupplierSettingTier.objects.get_or_create(
            supplier_setting=setting,
            tier=tier,
        )


def build_supplier_tiers_by_company(
    supplier_company_ids,
    tenant_account_id,
):
    """Per-supplier tier rows with SST pricing and active package original price."""
    if not supplier_company_ids:
        return {}

    from companies.models import Company

    account_by_supplier = {
        row['id']: row['account_id']
        for row in Company.objects.filter(id__in=supplier_company_ids).values(
            'id',
            'account_id',
        )
    }

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
        account_id = account_by_supplier.get(supplier_id)
        original_by_tier = (
            _original_prices_by_tier_id(
                company_id=supplier_id,
                account_id=account_id,
            )
            if account_id is not None
            else {}
        )
        existing = existing_by_supplier.get(supplier_id, {})
        tiers = _supplier_company_tiers_qs(supplier_id).order_by('name')
        result[supplier_id] = [
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
                'original_price': _decimal_to_api(original_by_tier.get(tier.id)),
            }
            for tier in tiers
        ]
    return result


def save_supplier_company_tier_pricing(
    supplier_company_id,
    tenant_account_id,
    tiers_data,
    *,
    supplier_account_id=None,
):
    """Persist discount, mark-up, types, and computed final price for each tier row."""
    from companies.models import Company

    if supplier_account_id is None:
        supplier_account_id = (
            Company.objects.filter(pk=supplier_company_id)
            .values_list('account_id', flat=True)
            .first()
        )

    original_by_tier = (
        _original_prices_by_tier_id(
            company_id=supplier_company_id,
            account_id=supplier_account_id,
        )
        if supplier_account_id is not None
        else {}
    )

    setting, _ = SupplierSetting.objects.get_or_create(
        supplier_id=supplier_company_id,
        account_id=tenant_account_id,
        defaults={'is_active': True},
    )

    valid_tier_ids = set(
        _supplier_company_tiers_qs(supplier_company_id).values_list('id', flat=True),
    )

    for item in tiers_data:
        tier_id = item.get('tier_id')
        if tier_id not in valid_tier_ids:
            continue
        tier_row, _ = SupplierSettingTier.objects.get_or_create(
            supplier_setting=setting,
            tier_id=tier_id,
        )
        discount = parse_price_value(item.get('discount'))
        mark_up = parse_price_value(item.get('mark_up'))
        discount_type = normalize_adjustment_type(item.get('discount_type'))
        mark_up_type = normalize_adjustment_type(item.get('mark_up_type'))
        original = original_by_tier.get(tier_id)
        tier_row.discount = discount
        tier_row.discount_type = discount_type
        tier_row.mark_up = mark_up
        tier_row.mark_up_type = mark_up_type
        tier_row.price = compute_tier_final_price(
            original,
            discount,
            discount_type,
            mark_up,
            mark_up_type,
        )
        tier_row.save(
            update_fields=[
                'discount',
                'discount_type',
                'mark_up',
                'mark_up_type',
                'price',
                'updated_at',
            ],
        )
