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
