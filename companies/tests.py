from django.test import TestCase

from companies.models import Company, CompanyKybVerification
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account


class CompanyMainFlagTests(TestCase):
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
        self.account = Account.objects.create(
            name='Test Account',
            country=country,
        )
        self.first = Company.objects.create(
            account=self.account,
            name='First Co',
            supplier_type=self.supplier_type,
            is_main=True,
        )
        self.second = Company.objects.create(
            account=self.account,
            name='Second Co',
            supplier_type=self.supplier_type,
            is_main=False,
        )

    def test_update_second_to_main_clears_first(self):
        self.second.is_main = True
        self.second.save(update_fields=['is_main'])

        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertFalse(self.first.is_main)
        self.assertTrue(self.second.is_main)
        self.assertEqual(
            Company.objects.filter(account=self.account, is_main=True).count(),
            1,
        )

    def test_create_main_clears_existing_main(self):
        third = Company(
            account=self.account,
            name='Third Co',
            supplier_type=self.supplier_type,
            is_main=True,
        )
        third.save()

        self.first.refresh_from_db()
        third.refresh_from_db()
        self.assertFalse(self.first.is_main)
        self.assertTrue(third.is_main)


class CompanyKybVerifiedTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='KYBland',
            iso_code='KYB',
            iso2_code='KB',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='Events')
        account = Account.objects.create(name='KYB Account', country=country)
        self.company = Company.objects.create(
            account=account,
            name='KYB Co',
            supplier_type=supplier_type,
        )

    def test_kyb_approved_sets_company_kyb_verified(self):
        kyb = CompanyKybVerification.objects.create(company=self.company)
        self.assertFalse(self.company.kyb_verified)

        kyb.status = CompanyKybVerification.Status.APPROVED
        kyb.save()

        self.company.refresh_from_db()
        self.assertTrue(self.company.kyb_verified)

    def test_kyb_rejected_clears_company_kyb_verified(self):
        kyb = CompanyKybVerification.objects.create(
            company=self.company,
            status=CompanyKybVerification.Status.APPROVED,
        )
        self.company.refresh_from_db()
        self.assertTrue(self.company.kyb_verified)

        kyb.status = CompanyKybVerification.Status.REJECTED
        kyb.save()

        self.company.refresh_from_db()
        self.assertFalse(self.company.kyb_verified)


class CompanyKybAdminApiTests(TestCase):
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
            name='Verify Me Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.kyb = CompanyKybVerification.objects.create(
            company=self.company,
            status=CompanyKybVerification.Status.SUBMITTED,
            business_type=CompanyKybVerification.BusinessType.SOLE_PROPRIETOR,
        )
        from users.models import User

        from users.test_support import grant_platform_admin

        self.admin = User.objects.create_user(
            username='admin@test.com',
            email='admin@test.com',
            password='test-pass',
            account=self.account,
            company=self.company,
        )
        grant_platform_admin(self.admin)
        self.user = User.objects.create_user(
            username='user@test.com',
            email='user@test.com',
            password='test-pass',
            account=self.account,
            company=self.company,
        )

    def test_admin_lists_submitted_kyb(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.get(
            '/api/admin/kyb-verifications/',
            {'status': CompanyKybVerification.Status.SUBMITTED},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['company_name'], 'Verify Me Co')

    def test_non_admin_cannot_list_kyb(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get('/api/admin/kyb-verifications/')
        self.assertEqual(res.status_code, 403)

    def test_admin_approves_kyb(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.patch(
            f'/api/admin/kyb-verifications/{self.kyb.pk}/',
            {'status': CompanyKybVerification.Status.APPROVED},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.kyb.refresh_from_db()
        self.assertEqual(self.kyb.status, CompanyKybVerification.Status.APPROVED)
        self.company.refresh_from_db()
        self.assertTrue(self.company.kyb_verified)
