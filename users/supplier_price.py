from decimal import Decimal, InvalidOperation



from django.db import transaction

from django.utils import timezone



from packages.models import PackagePrice, PackageVersion

from suppliers.models import Package, SupplierSetting, SupplierSettingPackage





def _supplier_company_packages_qs(supplier_company_id):

    return Package.objects.filter(

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

            is_active=True,

            effectivity_date__isnull=False,

            effectivity_date__lte=now,

        )

        .order_by('-effectivity_date', '-id')

        .first()

    )





def resolve_active_package_for_supplier_package(

    supplier_company_id: int,

    package_id: int,

) -> PackagePrice | None:

    """

    Active package price row for a supplier company + package: package must belong

    to that company; version must be active, in effect (effectivity_date <= now),

    not deleted; package price must be active and not deleted.

    """

    from companies.models import Company



    if not Package.objects.filter(

        pk=package_id,

        company_id=supplier_company_id,

        is_active=True,

        deleted_at__isnull=True,

    ).exists():

        return None

    account_id = (

        Company.objects.filter(pk=supplier_company_id)

        .values_list('account_id', flat=True)

        .first()

    )

    if account_id is None:

        return None

    version = _current_package_version_for_company(

        company_id=supplier_company_id,

        account_id=account_id,

    )

    if version is None:

        return None

    return (

        PackagePrice.objects.filter(

            company_id=supplier_company_id,

            package_id=package_id,

            package_version_id=version.id,

            is_active=True,

            deleted_at__isnull=True,

        ).first()

    )





def _original_prices_by_package_id(*, company_id, account_id):

    """Active package total_price per package for the current package version."""

    version = _current_package_version_for_company(

        company_id=company_id,

        account_id=account_id,

    )

    if version is None:

        return {}

    rows = PackagePrice.objects.filter(

        company_id=company_id,

        package_version_id=version.id,

        is_active=True,

        deleted_at__isnull=True,

    ).values('package_id', 'total_price')

    return {row['package_id']: row['total_price'] for row in rows}





def _required_downpayment_by_package_id(*, company_id, account_id):

    """Active package required_downpayment_amount per package for the current version."""

    version = _current_package_version_for_company(

        company_id=company_id,

        account_id=account_id,

    )

    if version is None:

        return {}

    rows = PackagePrice.objects.filter(

        company_id=company_id,

        package_version_id=version.id,

        is_active=True,

        deleted_at__isnull=True,

    ).values('package_id', 'required_downpayment_amount')

    return {

        row['package_id']: row['required_downpayment_amount']

        for row in rows

    }





def parse_price_value(value):

    if value is None or value == '':

        return None

    try:

        return Decimal(str(value))

    except (InvalidOperation, ValueError):

        return None





def normalize_adjustment_type(value):

    choices = SupplierSettingPackage.AdjustmentType

    if value in (choices.PERCENT, choices.FIXED):

        return value

    return choices.PERCENT





def _adjustment_amount(base, value, adjustment_type):

    if value is None:

        return Decimal('0')

    if adjustment_type == SupplierSettingPackage.AdjustmentType.FIXED:

        return value

    return (base * value) / Decimal('100')





def compute_package_final_price(

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





def _tenant_packages_qs(tenant_company_id):

    return Package.objects.filter(

        company_id=tenant_company_id,

        is_active=True,

        deleted_at__isnull=True,

    )





def set_supplier_package_pricing(

    supplier_company_id,

    tenant_account_id,

    tenant_company_id,

    *,

    package_id=None,

    price=None,

    price_unset=False,

):

    """

    Persist package selection and/or price on supplier_setting_packages for this tenant.



    ``price_unset`` is True when ``price`` was not included in the API payload.

    """

    setting, _ = SupplierSetting.objects.get_or_create(

        supplier_id=supplier_company_id,

        account_id=tenant_account_id,

        defaults={'is_active': True},

    )



    package_row = None

    if package_id is not None:

        package = _tenant_packages_qs(tenant_company_id).filter(pk=package_id).first()

        if package is None:

            return

        package_row, _ = SupplierSettingPackage.objects.get_or_create(

            supplier_setting=setting,

            package=package,

        )

    else:

        package_row = (

            SupplierSettingPackage.objects.filter(supplier_setting=setting)

            .order_by('-updated_at', 'package__name')

            .first()

        )



    if package_row is None:

        default_package = _tenant_packages_qs(tenant_company_id).order_by('name').first()

        if default_package is None:

            return

        package_row, _ = SupplierSettingPackage.objects.get_or_create(

            supplier_setting=setting,

            package=default_package,

        )



    update_fields = ['updated_at']

    if not price_unset:

        package_row.price = price

        update_fields.append('price')

    package_row.save(update_fields=update_fields)





def _decimal_to_api(value):

    if value is None:

        return None

    return format(value, 'f').rstrip('0').rstrip('.') or '0'





def get_booking_supplier_options(

    tenant_account_id,

    *,

    supplier_type_id=None,

    include_supplier_id=None,

):

    """

    Companies available on the booking supplier field: active supplier_settings

    for this tenant, optionally filtered by supplier type.

    """

    from companies.models import Company



    qs = (

        SupplierSetting.objects.filter(

            account_id=tenant_account_id,

            is_active=True,

            supplier__deleted_at__isnull=True,

            supplier__is_active=True,

        )

        .select_related('supplier')

        .order_by('supplier__sort_order', 'supplier__name', 'supplier_id')

    )

    if supplier_type_id is not None:

        qs = qs.filter(supplier__supplier_type_id=supplier_type_id)



    results = []

    seen_ids = set()

    for setting in qs:

        supplier = setting.supplier

        if supplier.id in seen_ids:

            continue

        seen_ids.add(supplier.id)

        results.append({

            'id': supplier.id,

            'name': supplier.name,

            'supplier_type_id': supplier.supplier_type_id,

            'kyb_verified': supplier.kyb_verified,

        })



    if include_supplier_id is not None and include_supplier_id not in seen_ids:

        company = (

            Company.objects.filter(

                pk=include_supplier_id,

                deleted_at__isnull=True,

            )

            .select_related('supplier_type')

            .first()

        )

        if company is not None:

            results.insert(

                0,

                {

                    'id': company.id,

                    'name': company.name,

                    'supplier_type_id': company.supplier_type_id,

                    'kyb_verified': company.kyb_verified,

                },

            )

    return results





def get_supplier_company_package_options(

    supplier_company_id,

    tenant_account_id,

    tenant_company_id=None,

):

    """Packages from supplier_setting_packages for an active supplier setting."""

    del tenant_company_id  # kept for call-site compatibility



    setting = SupplierSetting.objects.filter(

        supplier_id=supplier_company_id,

        account_id=tenant_account_id,

        is_active=True,

    ).first()

    if setting is None:

        return []



    default_type = SupplierSettingPackage.AdjustmentType.PERCENT

    rows = (

        SupplierSettingPackage.objects.filter(supplier_setting=setting)

        .select_related('package')

        .order_by('package__name', 'id')

    )

    from companies.models import Company



    supplier_account_id = (

        Company.objects.filter(pk=supplier_company_id)

        .values_list('account_id', flat=True)

        .first()

    )

    downpayment_by_package = (

        _required_downpayment_by_package_id(

            company_id=supplier_company_id,

            account_id=supplier_account_id,

        )

        if supplier_account_id is not None

        else {}

    )

    active_version = (

        _current_package_version_for_company(

            company_id=supplier_company_id,

            account_id=supplier_account_id,

        )

        if supplier_account_id is not None

        else None

    )

    active_version_id = active_version.id if active_version is not None else None

    original_by_package = (

        _original_prices_by_package_id(

            company_id=supplier_company_id,

            account_id=supplier_account_id,

        )

        if supplier_account_id is not None

        else {}

    )

    package_price_by_package: dict[int, dict] = {}

    if active_version_id is not None:

        package_price_by_package = {

            row['package_id']: row

            for row in PackagePrice.objects.filter(

                company_id=supplier_company_id,

                package_version_id=active_version_id,

                is_active=True,

                deleted_at__isnull=True,

            ).values('id', 'package_id')

        }

    result = []

    for row in rows:

        package = row.package

        if not package.is_active or package.deleted_at is not None:

            continue

        pkg = package_price_by_package.get(package.id)

        original = original_by_package.get(package.id)

        if row.price is not None:

            line_price = row.price

        else:

            line_price = compute_package_final_price(

                original,

                row.discount,

                row.discount_type or default_type,

                row.mark_up,

                row.mark_up_type or default_type,

            )

            if line_price is None and original is not None:

                line_price = original

        result.append({

            'id': package.id,

            'name': package.name,

            'is_active': package.is_active,

            'discount': _decimal_to_api(row.discount),

            'discount_type': row.discount_type or default_type,

            'mark_up': _decimal_to_api(row.mark_up),

            'mark_up_type': row.mark_up_type or default_type,

            'price_override': _decimal_to_api(row.price_override),

            'tax': _decimal_to_api(row.tax),

            'price': _decimal_to_api(line_price),

            'package_total_price': _decimal_to_api(original),

            'required_downpayment_amount': _decimal_to_api(

                downpayment_by_package.get(package.id),

            ),

            'package_price_id': pkg['id'] if pkg is not None else None,

            'package_version_id': active_version_id,

        })

    return result





def resolve_supplier_package_booking_price(

    supplier_company_id: int,

    package_id: int,

    tenant_account_id: int,

):

    """Quotation line price for a supplier package (SST price or package total)."""

    for row in get_supplier_company_package_options(

        supplier_company_id,

        tenant_account_id,

    ):

        if row['id'] == package_id:

            return parse_price_value(row.get('price'))

    package_price = resolve_active_package_for_supplier_package(

        supplier_company_id,

        package_id,

    )

    if package_price is not None:

        return package_price.total_price

    return None





def get_supplier_company_package_pricing(

    supplier_company_id,

    tenant_account_id,

    *,

    supplier_account_id=None,

):

    """

    Active packages for the supplier company with SST pricing and package original price.

    """

    from companies.models import Company



    if supplier_account_id is None:

        supplier_account_id = (

            Company.objects.filter(pk=supplier_company_id)

            .values_list('account_id', flat=True)

            .first()

        )



    packages = _supplier_company_packages_qs(supplier_company_id).order_by('name')

    original_by_package = (

        _original_prices_by_package_id(

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

        for row in SupplierSettingPackage.objects.filter(supplier_setting=setting):

            existing[row.package_id] = row



    default_type = SupplierSettingPackage.AdjustmentType.PERCENT

    return [

        {

            'package_id': package.id,

            'package_name': package.name,

            'discount': _decimal_to_api(existing[package.id].discount)

            if package.id in existing

            else None,

            'discount_type': existing[package.id].discount_type

            if package.id in existing

            else default_type,

            'mark_up': _decimal_to_api(existing[package.id].mark_up)

            if package.id in existing

            else None,

            'mark_up_type': existing[package.id].mark_up_type

            if package.id in existing

            else default_type,

            'price': _decimal_to_api(existing[package.id].price)

            if package.id in existing

            else None,

            'original_price': _decimal_to_api(original_by_package.get(package.id)),

        }

        for package in packages

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

    """Upsert supplier_settings and supplier_setting_packages for all supplier packages."""

    setting, _ = SupplierSetting.objects.get_or_create(

        supplier_id=supplier_company_id,

        account_id=tenant_account_id,

        defaults={'is_active': is_active},

    )

    setting.is_active = is_active

    setting.save(update_fields=['is_active', 'updated_at'])



    for package in _supplier_company_packages_qs(supplier_company_id):

        SupplierSettingPackage.objects.get_or_create(

            supplier_setting=setting,

            package=package,

        )





def build_supplier_packages_by_company(

    supplier_company_ids,

    tenant_account_id,

):

    """Per-supplier package rows with SST pricing and active package original price."""

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

    ).prefetch_related('packages')



    existing_by_supplier = {}

    for setting in settings:

        existing_by_supplier[setting.supplier_id] = {

            row.package_id: row for row in setting.packages.all()

        }



    result = {}

    for supplier_id in supplier_company_ids:

        account_id = account_by_supplier.get(supplier_id)

        original_by_package = (

            _original_prices_by_package_id(

                company_id=supplier_id,

                account_id=account_id,

            )

            if account_id is not None

            else {}

        )

        existing = existing_by_supplier.get(supplier_id, {})

        packages = _supplier_company_packages_qs(supplier_id).order_by('name')

        default_type = SupplierSettingPackage.AdjustmentType.PERCENT

        result[supplier_id] = [

            {

                'package_id': package.id,

                'package_name': package.name,

                'discount': _decimal_to_api(existing[package.id].discount)

                if package.id in existing

                else None,

                'discount_type': existing[package.id].discount_type

                if package.id in existing

                else default_type,

                'mark_up': _decimal_to_api(existing[package.id].mark_up)

                if package.id in existing

                else None,

                'mark_up_type': existing[package.id].mark_up_type

                if package.id in existing

                else default_type,

                'price': _decimal_to_api(existing[package.id].price)

                if package.id in existing

                else None,

                'original_price': _decimal_to_api(original_by_package.get(package.id)),

            }

            for package in packages

        ]

    return result





def save_supplier_company_package_pricing(

    supplier_company_id,

    tenant_account_id,

    packages_data,

    *,

    supplier_account_id=None,

):

    """Persist discount, mark-up, types, and computed final price for each package row."""

    from companies.models import Company



    if supplier_account_id is None:

        supplier_account_id = (

            Company.objects.filter(pk=supplier_company_id)

            .values_list('account_id', flat=True)

            .first()

        )



    original_by_package = (

        _original_prices_by_package_id(

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



    valid_package_ids = set(

        _supplier_company_packages_qs(supplier_company_id).values_list('id', flat=True),

    )



    for item in packages_data:

        package_id = item.get('package_id')

        if package_id not in valid_package_ids:

            continue

        package_row, _ = SupplierSettingPackage.objects.get_or_create(

            supplier_setting=setting,

            package_id=package_id,

        )

        discount = parse_price_value(item.get('discount'))

        mark_up = parse_price_value(item.get('mark_up'))

        discount_type = normalize_adjustment_type(item.get('discount_type'))

        mark_up_type = normalize_adjustment_type(item.get('mark_up_type'))

        original = original_by_package.get(package_id)

        package_row.discount = discount

        package_row.discount_type = discount_type

        package_row.mark_up = mark_up

        package_row.mark_up_type = mark_up_type

        package_row.price = compute_package_final_price(

            original,

            discount,

            discount_type,

            mark_up,

            mark_up_type,

        )

        package_row.save(

            update_fields=[

                'discount',

                'discount_type',

                'mark_up',

                'mark_up_type',

                'price',

                'updated_at',

            ],

        )

