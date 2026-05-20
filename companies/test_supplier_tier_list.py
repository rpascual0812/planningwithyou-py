from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from countries.models import Country
from packages.models import Package, PackageVersion
from suppliers.models import (
    SupplierSetting,
    SupplierSettingTier,
    SupplierType,
    Tier,
)
from users.models import Account
from users.supplier_price import (
    build_supplier_setting_active_by_company,
    build_supplier_tiers_by_company,
    compute_tier_final_price,
    save_supplier_company_tier_pricing,
    set_supplier_setting_active,
)
from suppliers.models import SupplierSettingTier


class SupplierTierListPricingTests(TestCase):
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
        self.tier_a = Tier.objects.create(
            account=self.tenant_account,
            company=self.supplier,
            name='Gold',
        )
        self.tier_b = Tier.objects.create(
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
        Package.objects.create(
            package_version=self.current_version,
            tier=self.tier_a,
            company=self.supplier,
            account=self.tenant_account,
            total_price=Decimal('100.00'),
            is_active=True,
        )
        Package.objects.create(
            package_version=self.old_version,
            tier=self.tier_b,
            company=self.supplier,
            account=self.tenant_account,
            total_price=Decimal('50.00'),
            is_active=True,
        )
        setting = SupplierSetting.objects.create(
            supplier=self.supplier,
            account=self.tenant_account,
        )
        SupplierSettingTier.objects.create(
            supplier_setting=setting,
            tier=self.tier_a,
            price=Decimal('120.00'),
        )

    def test_build_supplier_tiers_uses_company_tiers_and_current_package(self):
        rows = build_supplier_tiers_by_company(
            [self.supplier.id],
            self.tenant_account.id,
        )[self.supplier.id]
        by_name = {row['tier_name']: row for row in rows}
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

    def test_toggle_active_upserts_supplier_setting_tiers(self):
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
        tier_ids = set(
            SupplierSettingTier.objects.filter(supplier_setting=setting).values_list(
                'tier_id',
                flat=True,
            ),
        )
        self.assertEqual(tier_ids, {self.tier_a.id, self.tier_b.id})

    def test_compute_tier_final_price_no_adjustments(self):
        self.assertEqual(
            compute_tier_final_price(Decimal('100'), None, 'percent', None, 'percent'),
            Decimal('100'),
        )

    def test_compute_tier_final_price_percent_discount_and_markup(self):
        self.assertEqual(
            compute_tier_final_price(
                Decimal('100'),
                Decimal('10'),
                'percent',
                Decimal('5'),
                'percent',
            ),
            Decimal('95'),
        )

    def test_compute_tier_final_price_fixed_discount(self):
        self.assertEqual(
            compute_tier_final_price(
                Decimal('100'),
                Decimal('15'),
                'fixed',
                None,
                'percent',
            ),
            Decimal('85'),
        )

    def test_save_tier_pricing_persists_computed_price(self):
        save_supplier_company_tier_pricing(
            self.supplier.id,
            self.tenant_account.id,
            [
                {
                    'tier_id': self.tier_a.id,
                    'discount': '10',
                    'discount_type': 'percent',
                    'mark_up': '5',
                    'mark_up_type': 'fixed',
                },
            ],
            supplier_account_id=self.supplier.account_id,
        )
        row = SupplierSettingTier.objects.get(
            supplier_setting__supplier_id=self.supplier.id,
            tier_id=self.tier_a.id,
        )
        self.assertEqual(row.discount, Decimal('10'))
        self.assertEqual(row.discount_type, 'percent')
        self.assertEqual(row.mark_up, Decimal('5'))
        self.assertEqual(row.mark_up_type, 'fixed')
        self.assertEqual(row.price, Decimal('95'))
