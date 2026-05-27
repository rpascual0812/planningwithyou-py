from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import History
from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class CompanyHistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.create(
            name='Philippines',
            iso_code='PHL',
            iso2_code='PH',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        cls.supplier_type = SupplierType.objects.create(name='Planner')

    def setUp(self):
        self.client = APIClient()
        self.account = Account.objects.create(
            name='Tenant',
            country=self.country,
            is_active=True,
        )
        self.company = Company.objects.create(
            account=self.account,
            name='Main Co',
            supplier_type=self.supplier_type,
            is_main=True,
            is_active=True,
        )
        self.user = User.objects.create_user(
            username='editor@test.example',
            email='editor@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_update_company_records_history(self):
        res = self.client.patch(
            f'/companies/{self.company.pk}/',
            {'name': 'Renamed Co'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.get(
            resource_type=History.ResourceType.COMPANY,
            resource_id=self.company.pk,
            action=History.Action.UPDATE,
        )
        self.assertEqual(entry.changes['fields']['name']['old'], 'Main Co')
        self.assertEqual(entry.changes['fields']['name']['new'], 'Renamed Co')

    def test_company_history_list_endpoint(self):
        History.objects.create(
            account_id=self.account.pk,
            resource_type=History.ResourceType.COMPANY,
            resource_id=self.company.pk,
            entity_type=History.EntityType.COMPANY,
            entity_id=self.company.pk,
            action=History.Action.UPDATE,
            actor=self.user,
            changes={'fields': {'name': {'old': 'A', 'new': 'B'}}},
        )
        res = self.client.get(f'/companies/{self.company.pk}/history/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
