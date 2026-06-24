from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from countries.models import Country
from packages.models import PackagePrice, PackageVersion
from suppliers.models import (
    Package,
    SupplierSetting,
    SupplierSettingPackage,
    SupplierType,
)
from users.models import Account
from users.supplier_price import (
    build_supplier_packages_by_company,
    build_supplier_setting_active_by_company,
    compute_package_final_price,
    save_supplier_company_package_pricing,
    set_supplier_setting_active,
)


class SupplierPackageListPricingTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        self.supplier_type = SupplierType.objects.create(name='General')
        self.tenant_account = Account.objects.create(name='Tenant', country=country)
        self.tenant_company = Company.objects.create(
            account=self.tenant_account,
            name='Tenant Co',
            supplier_type=self.supplier_type,
            is_main=True,
        )
        self.supplier = Company.objects.create(
            account=self.tenant_account,
            name='Supplier Co',
            supplier_type=self.supplier_type,
        )
        self.package_a = Package.objects.create(
            account=self.tenant_account,
            company=self.supplier,
            name='Gold',
        )
        self.package_b = Package.objects.create(
            account=self.tenant_account,
            company=self.supplier,
            name='Silver',
        )
        past = timezone.now() - timedelta(days=30)
        self.old_version = PackageVersion.objects.create(
            title='Old',
            effectivity_date=past - timedelta(days=10),
            company=self.supplier,
            account=self.tenant_account,
        )
        self.current_version = PackageVersion.objects.create(
            title='Current',
            effectivity_date=past,
            company=self.supplier,
            account=self.tenant_account,
        )
        PackagePrice.objects.create(
            package_version=self.current_version,
            package=self.package_a,
            company=self.supplier,
            account=self.tenant_account,
            total_price=Decimal('100.00'),
            is_active=True,
        )
        PackagePrice.objects.create(
            package_version=self.old_version,
            package=self.package_b,
            company=self.supplier,
            account=self.tenant_account,
            total_price=Decimal('50.00'),
            is_active=True,
        )
        setting = SupplierSetting.objects.create(
            supplier=self.supplier,
            account=self.tenant_account,
        )
        SupplierSettingPackage.objects.create(
            supplier_setting=setting,
            package=self.package_a,
            price=Decimal('120.00'),
        )

    def test_build_supplier_packages_uses_company_packages_and_current_package(self):
        rows = build_supplier_packages_by_company(
            [self.supplier.id],
            self.tenant_account.id,
        )[self.supplier.id]
        by_name = {row['package_name']: row for row in rows}
        self.assertEqual(by_name['Gold']['original_price'], '100')
        self.assertEqual(by_name['Gold']['price'], '120')
        self.assertIsNone(by_name['Silver']['original_price'])
        self.assertIsNone(by_name['Silver']['price'])

    def test_supplier_setting_active_defaults_false_without_row(self):
        active = build_supplier_setting_active_by_company(
            [self.supplier.id],
            self.tenant_account.id,
        )
        self.assertFalse(active[self.supplier.id])

    def test_supplier_setting_active_persisted_separately_from_company(self):
        self.supplier.is_active = True
        self.supplier.save(update_fields=['is_active'])
        set_supplier_setting_active(
            self.supplier.id,
            self.tenant_account.id,
            False,
        )
        active = build_supplier_setting_active_by_company(
            [self.supplier.id],
            self.tenant_account.id,
        )
        self.assertFalse(active[self.supplier.id])
        self.supplier.refresh_from_db()
        self.assertTrue(self.supplier.is_active)

    def test_toggle_active_upserts_supplier_setting_packages(self):
        set_supplier_setting_active(
            self.supplier.id,
            self.tenant_account.id,
            True,
        )
        setting = SupplierSetting.objects.get(
            supplier_id=self.supplier.id,
            account_id=self.tenant_account.id,
        )
        self.assertTrue(setting.is_active)
        package_ids = set(
            SupplierSettingPackage.objects.filter(supplier_setting=setting).values_list(
                'package_id',
                flat=True,
            ),
        )
        self.assertEqual(package_ids, {self.package_a.id, self.package_b.id})

    def test_compute_package_final_price_no_adjustments(self):
        self.assertEqual(
            compute_package_final_price(Decimal('100'), None, 'percent', None, 'percent'),
            Decimal('100'),
        )

    def test_compute_package_final_price_percent_discount_and_markup(self):
        self.assertEqual(
            compute_package_final_price(
                Decimal('100'),
                Decimal('10'),
                'percent',
                Decimal('5'),
                'percent',
            ),
            Decimal('95'),
        )

    def test_compute_package_final_price_fixed_discount(self):
        self.assertEqual(
            compute_package_final_price(
                Decimal('100'),
                Decimal('15'),
                'fixed',
                None,
                'percent',
            ),
            Decimal('85'),
        )

    def test_save_package_pricing_persists_computed_price(self):
        save_supplier_company_package_pricing(
            self.supplier.id,
            self.tenant_account.id,
            [
                {
                    'package_id': self.package_a.id,
                    'discount': '10',
                    'discount_type': 'percent',
                    'mark_up': '5',
                    'mark_up_type': 'fixed',
                },
            ],
            supplier_account_id=self.supplier.account_id,
        )
        row = SupplierSettingPackage.objects.get(
            supplier_setting__supplier_id=self.supplier.id,
            package_id=self.package_a.id,
        )
        self.assertEqual(row.discount, Decimal('10'))
        self.assertEqual(row.discount_type, 'percent')
        self.assertEqual(row.mark_up, Decimal('5'))
        self.assertEqual(row.mark_up_type, 'fixed')
        self.assertEqual(row.price, Decimal('95'))
