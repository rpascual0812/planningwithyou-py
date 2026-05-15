from decimal import Decimal, InvalidOperation

from suppliers.models import SupplierSetting, SupplierSettingTier


def supplier_accounts_with_price_queryset(qs, tenant_account_id):
    """Annotate supplier accounts with price from supplier_setting_tiers."""
    from django.db.models import OuterRef, Subquery

    price_sq = SupplierSettingTier.objects.filter(
        supplier_setting__supplier_id=OuterRef('pk'),
        supplier_setting__account_id=tenant_account_id,
    ).order_by('tier__name').values('price')[:1]

    return qs.annotate(price=Subquery(price_sq))


def parse_price_value(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def set_supplier_account_price(supplier_account_id, tenant_account_id, price):
    """Persist price on the first tier row (by tier name) for this supplier setting."""
    setting = SupplierSetting.objects.filter(
        supplier_id=supplier_account_id,
        account_id=tenant_account_id,
    ).first()
    if not setting:
        return

    tier_row = (
        SupplierSettingTier.objects.filter(supplier_setting=setting)
        .order_by('tier__name')
        .first()
    )
    if not tier_row:
        return

    tier_row.price = price
    tier_row.save(update_fields=['price', 'updated_at'])
