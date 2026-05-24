from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from packages.models import Package, PackageItem, PackageVersion
from suppliers.models import (
    SupplierSetting,
    SupplierSettingTier,
    SupplierType,
    Tier,
)
from users.models import Account, User


class BookingSupplierPackageViewTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(name='Tenant', country=country)
        self.company = Company.objects.create(
            account=self.account,
            name='Tenant Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.supplier = Company.objects.create(
            account=self.account,
            name='Supplier Co',
            supplier_type=supplier_type,
        )
        self.tier = Tier.objects.create(
            account=self.account,
            company=self.supplier,
            name='Gold',
        )
        past = timezone.now() - timedelta(days=1)
        self.version = PackageVersion.objects.create(
            title='Current',
            effectivity_date=past,
            company=self.supplier,
            account=self.account,
        )
        self.package = Package.objects.create(
            package_version=self.version,
            tier=self.tier,
            company=self.supplier,
            account=self.account,
            total_price=Decimal('100.00'),
            is_active=True,
        )
        self.item = PackageItem.objects.create(
            package=self.package,
            account=self.account,
            company=self.supplier,
            title='Main dish',
            sort_order=0,
        )
        setting = SupplierSetting.objects.create(
            supplier=self.supplier,
            account=self.account,
            is_active=True,
        )
        SupplierSettingTier.objects.create(
            supplier_setting=setting,
            tier=self.tier,
            price=Decimal('120.00'),
        )
        self.user = User.objects.create_user(
            username='booking-pkg@test.com',
            email='booking-pkg@test.com',
            password='test-pass',
            account=self.account,
            company=self.company,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_returns_package_items_same_as_pdf_resolution(self):
        res = self.client.get(
            '/api/booking-supplier-package/',
            {
                'company_id': self.supplier.id,
                'tier_id': self.tier.id,
                'package_version_id': self.version.id,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['id'], self.package.id)
        self.assertEqual(len(res.data['items']), 1)
        self.assertEqual(res.data['items'][0]['title'], 'Main dish')

    def test_resolves_active_package_when_version_omitted(self):
        res = self.client.get(
            '/api/booking-supplier-package/',
            {
                'company_id': self.supplier.id,
                'tier_id': self.tier.id,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['id'], self.package.id)
        self.assertEqual(len(res.data['items']), 1)

    def test_allows_supplier_company_linked_via_supplier_setting_only(self):
        """Supplier company may share the tenant account but validation uses SupplierSetting."""
        other_account = Account.objects.create(
            name='Other',
            country=Country.objects.get(pk=self.account.country_id),
        )
        external_supplier = Company.objects.create(
            account=other_account,
            name='External Supplier',
            supplier_type=SupplierType.objects.get(pk=self.supplier.supplier_type_id),
        )
        external_tier = Tier.objects.create(
            account=other_account,
            company=external_supplier,
            name='Platinum',
        )
        SupplierSetting.objects.create(
            supplier=external_supplier,
            account=self.account,
            is_active=True,
        )
        past = timezone.now() - timedelta(days=1)
        version = PackageVersion.objects.create(
            title='External',
            effectivity_date=past,
            company=external_supplier,
            account=other_account,
        )
        Package.objects.create(
            package_version=version,
            tier=external_tier,
            company=external_supplier,
            account=other_account,
            total_price=Decimal('200.00'),
            is_active=True,
        )
        PackageItem.objects.create(
            package=Package.objects.get(tier=external_tier),
            account=other_account,
            company=external_supplier,
            title='External item',
        )
        res = self.client.get(
            '/api/booking-supplier-package/',
            {
                'company_id': external_supplier.id,
                'tier_id': external_tier.id,
                'package_version_id': version.id,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['items'][0]['title'], 'External item')

    def test_nested_items_match_pdf_tree(self):
        root = PackageItem.objects.create(
            package=self.package,
            account=self.account,
            company=self.supplier,
            title='Root service',
            sort_order=1,
        )
        PackageItem.objects.create(
            package=self.package,
            parent=root,
            account=self.account,
            company=self.supplier,
            title='Sub item',
            sort_order=0,
        )
        res = self.client.get(
            '/api/booking-supplier-package/',
            {
                'company_id': self.supplier.id,
                'tier_id': self.tier.id,
            },
        )
        self.assertEqual(res.status_code, 200)
        roots = res.data['items']
        root_titles = {row['title'] for row in roots}
        self.assertIn('Main dish', root_titles)
        self.assertIn('Root service', root_titles)
        root_row = next(r for r in roots if r['title'] == 'Root service')
        self.assertEqual(len(root_row['children']), 1)
        self.assertEqual(root_row['children'][0]['title'], 'Sub item')
