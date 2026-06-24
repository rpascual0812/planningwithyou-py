from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from packages.models import Package, PackageVersion
from suppliers.models import SupplierType, Tier
from users.models import Account
from users.test_support import assign_owner_role

User = get_user_model()


class PackageActivationTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Packland',
            iso_code='PKL',
            iso2_code='PL',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='Events')
        self.account = Account.objects.create(name='Package Account', country=country)
        self.company = Company.objects.create(
            account=self.account,
            name='Package Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.tier = Tier.objects.create(
            account=self.account,
            company=self.company,
            name='Gold',
        )
        self.other_tier = Tier.objects.create(
            account=self.account,
            company=self.company,
            name='Silver',
        )
        self.version = PackageVersion.objects.create(
            account=self.account,
            company=self.company,
            title='2026',
            effectivity_date=timezone.now(),
            is_active=True,
        )
        self.other_version = PackageVersion.objects.create(
            account=self.account,
            company=self.company,
            title='2025',
            effectivity_date=timezone.now(),
            is_active=True,
        )
        self.user = User.objects.create_user(
            username='owner@packages.test',
            email='owner@packages.test',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        assign_owner_role(self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _create_package(self, *, tier=None, version=None, description='Package', is_active=True):
        return Package.objects.create(
            account=self.account,
            company=self.company,
            tier=tier or self.tier,
            package_version=version or self.version,
            description=description,
            total_price=Decimal('1000.00'),
            required_downpayment_amount=Decimal('0.00'),
            is_active=is_active,
            created_by=self.user,
        )

    def test_update_active_package_deactivates_siblings(self):
        first = self._create_package(description='First')
        second = self._create_package(description='Second', is_active=False)

        res = self.client.patch(
            f'/packages/{second.id}/',
            {'is_active': True},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)

    def test_create_active_package_deactivates_existing(self):
        existing = self._create_package(description='Existing')

        res = self.client.post(
            '/packages/',
            {
                'company': self.company.id,
                'tier': self.tier.id,
                'package_version': self.version.id,
                'description': 'New active',
                'total_price': '1500.00',
                'required_downpayment_amount': '0.00',
                'is_active': True,
                'items': [],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)

        existing.refresh_from_db()
        self.assertFalse(existing.is_active)
        self.assertTrue(
            Package.objects.filter(
                company=self.company,
                tier=self.tier,
                package_version=self.version,
                is_active=True,
            ).count(),
            1,
        )

    def test_activation_does_not_affect_other_tier_or_version(self):
        same_tier_other_version = self._create_package(
            description='Other version',
            version=self.other_version,
        )
        other_tier_same_version = self._create_package(
            description='Other tier',
            tier=self.other_tier,
        )
        target = self._create_package(description='Target', is_active=False)

        res = self.client.patch(
            f'/packages/{target.id}/',
            {'is_active': True},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)

        same_tier_other_version.refresh_from_db()
        other_tier_same_version.refresh_from_db()
        target.refresh_from_db()
        self.assertTrue(same_tier_other_version.is_active)
        self.assertTrue(other_tier_same_version.is_active)
        self.assertTrue(target.is_active)
