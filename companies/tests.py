from django.test import TestCase

from companies.models import Company
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
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(
            name='Test Account',
            country=country,
            supplier_type=supplier_type,
        )
        self.first = Company.objects.create(
            account=self.account,
            name='First Co',
            is_main=True,
        )
        self.second = Company.objects.create(
            account=self.account,
            name='Second Co',
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
            is_main=True,
        )
        third.save()

        self.first.refresh_from_db()
        third.refresh_from_db()
        self.assertFalse(self.first.is_main)
        self.assertTrue(third.is_main)
