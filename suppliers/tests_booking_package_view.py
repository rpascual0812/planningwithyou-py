from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from packages.models import PackagePrice, PackageItem, PackageVersion
from suppliers.models import (
    SupplierSetting,
    SupplierSettingPackage,
    SupplierType,
    Package,
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
        self.package = Package.objects.create(
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
        self.package_price = PackagePrice.objects.create(
            package_version=self.version,
            package=self.package,
            company=self.supplier,
            account=self.account,
            total_price=Decimal('100.00'),
            is_active=True,
        )
        self.item = PackageItem.objects.create(
            package_price=self.package_price,
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
        SupplierSettingPackage.objects.create(
            supplier_setting=setting,
            package=self.package,
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
            '/booking-supplier-package/',
            {
                'company_id': self.supplier.id,
                'package_id': self.package.id,
                'package_version_id': self.version.id,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['id'], self.package_price.id)
        self.assertEqual(len(res.data['items']), 1)
        self.assertEqual(res.data['items'][0]['title'], 'Main dish')

    def test_resolves_active_package_when_version_omitted(self):
        res = self.client.get(
            '/booking-supplier-package/',
            {
                'company_id': self.supplier.id,
                'package_id': self.package.id,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['id'], self.package_price.id)
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
        external_package = Package.objects.create(
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
        PackagePrice.objects.create(
            package_version=version,
            package=external_package,
            company=external_supplier,
            account=other_account,
            total_price=Decimal('200.00'),
            is_active=True,
        )
        PackageItem.objects.create(
            package_price=PackagePrice.objects.get(package=external_package),
            account=other_account,
            company=external_supplier,
            title='External item',
        )
        res = self.client.get(
            '/booking-supplier-package/',
            {
                'company_id': external_supplier.id,
                'package_id': external_package.id,
                'package_version_id': version.id,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['items'][0]['title'], 'External item')

    def test_nested_items_match_pdf_tree(self):
        root = PackageItem.objects.create(
            package_price=self.package_price,
            account=self.account,
            company=self.supplier,
            title='Root service',
            sort_order=1,
        )
        PackageItem.objects.create(
            package_price=self.package_price,
            parent=root,
            account=self.account,
            company=self.supplier,
            title='Sub item',
            sort_order=0,
        )
        res = self.client.get(
            '/booking-supplier-package/',
            {
                'company_id': self.supplier.id,
                'package_id': self.package.id,
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
