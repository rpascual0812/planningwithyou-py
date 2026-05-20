from decimal import Decimal

from django.test import TestCase

from companies.models import Company
from countries.models import Country
from suppliers.models import (
    SupplierSetting,
    SupplierSettingTier,
    SupplierType,
    Tier,
)
from users.models import Account
from users.supplier_price import (
    get_booking_supplier_options,
    get_supplier_company_tier_options,
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
        self.tier = Tier.objects.create(
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
        SupplierSettingTier.objects.create(
            supplier_setting=active_setting,
            tier=self.tier,
            price=Decimal('250.00'),
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
        rows = get_supplier_company_tier_options(
            self.active_supplier.id,
            self.tenant_account.id,
            self.tenant_company.id,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'Gold')
        self.assertEqual(rows[0]['price'], '250')

    def test_tier_options_empty_when_setting_inactive(self):
        rows = get_supplier_company_tier_options(
            self.inactive_setting_supplier.id,
            self.tenant_account.id,
            self.tenant_company.id,
        )
        self.assertEqual(rows, [])
