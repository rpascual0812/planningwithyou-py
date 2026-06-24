from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from countries.models import Country
from packages.models import PackagePrice, PackageVersion
from suppliers.models import (
    SupplierSetting,
    SupplierSettingPackage,
    SupplierType,
    Package,
)
from users.models import Account
from users.supplier_price import (
    get_booking_supplier_options,
    get_supplier_company_package_options,
)


class BookingSupplierFieldOptionsTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        self.supplier_type_a = SupplierType.objects.create(name='Florist')
        self.supplier_type_b = SupplierType.objects.create(name='Caterer')
        self.tenant_account = Account.objects.create(name='Tenant', country=country)
        self.tenant_company = Company.objects.create(
            account=self.tenant_account,
            name='Tenant Co',
            supplier_type=self.supplier_type_a,
            is_main=True,
        )
        self.active_supplier = Company.objects.create(
            account=self.tenant_account,
            name='Active Florist',
            supplier_type=self.supplier_type_a,
        )
        self.inactive_setting_supplier = Company.objects.create(
            account=self.tenant_account,
            name='Inactive Florist',
            supplier_type=self.supplier_type_a,
        )
        self.other_type_supplier = Company.objects.create(
            account=self.tenant_account,
            name='Active Caterer',
            supplier_type=self.supplier_type_b,
        )
        self.package = Package.objects.create(
            account=self.tenant_account,
            company=self.active_supplier,
            name='Gold',
        )
        active_setting = SupplierSetting.objects.create(
            supplier=self.active_supplier,
            account=self.tenant_account,
            is_active=True,
        )
        SupplierSetting.objects.create(
            supplier=self.inactive_setting_supplier,
            account=self.tenant_account,
            is_active=False,
        )
        SupplierSetting.objects.create(
            supplier=self.other_type_supplier,
            account=self.tenant_account,
            is_active=True,
        )
        SupplierSettingPackage.objects.create(
            supplier_setting=active_setting,
            package=self.package,
            price=Decimal('250.00'),
        )
        past = timezone.now() - timedelta(days=1)
        self.package_version = PackageVersion.objects.create(
            title='Current',
            effectivity_date=past,
            company=self.active_supplier,
            account=self.tenant_account,
        )
        self.package_price = PackagePrice.objects.create(
            package_version=self.package_version,
            package=self.package,
            company=self.active_supplier,
            account=self.tenant_account,
            total_price=Decimal('100.00'),
            is_active=True,
        )

    def test_booking_supplier_options_only_active_settings(self):
        options = get_booking_supplier_options(self.tenant_account.id)
        names = {row['name'] for row in options}
        self.assertIn('Active Florist', names)
        self.assertIn('Active Caterer', names)
        self.assertNotIn('Inactive Florist', names)

    def test_booking_supplier_options_filter_by_type(self):
        options = get_booking_supplier_options(
            self.tenant_account.id,
            supplier_type_id=self.supplier_type_a.id,
        )
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]['name'], 'Active Florist')
        self.assertEqual(options[0]['supplier_type_id'], self.supplier_type_a.id)

    def test_tier_options_use_supplier_setting_tier_price(self):
        rows = get_supplier_company_package_options(
            self.active_supplier.id,
            self.tenant_account.id,
            self.tenant_company.id,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'Gold')
        self.assertEqual(rows[0]['price'], '250')
        self.assertEqual(rows[0]['package_total_price'], '100')
        self.assertEqual(rows[0]['package_price_id'], self.package_price.id)
        self.assertEqual(rows[0]['package_version_id'], self.package_version.id)

    def test_tier_options_fall_back_to_package_total_when_price_unset(self):
        SupplierSettingPackage.objects.filter(
            supplier_setting__supplier_id=self.active_supplier.id,
            package_id=self.package.id,
        ).update(price=None)
        rows = get_supplier_company_package_options(
            self.active_supplier.id,
            self.tenant_account.id,
            self.tenant_company.id,
        )
        self.assertEqual(rows[0]['price'], '100')
        self.assertEqual(rows[0]['package_total_price'], '100')

    def test_tier_options_empty_when_setting_inactive(self):
        rows = get_supplier_company_package_options(
            self.inactive_setting_supplier.id,
            self.tenant_account.id,
            self.tenant_company.id,
        )
        self.assertEqual(rows, [])
