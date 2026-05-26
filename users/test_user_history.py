from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import History
from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account
from users.test_support import assign_owner_role

User = get_user_model()


class UserHistoryTests(TestCase):
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
        self.admin = User.objects.create_user(
            username='admin@test.example',
            email='admin@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        assign_owner_role(self.admin)
        self.target = User.objects.create_user(
            username='member@test.example',
            email='member@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
            first_name='Old',
        )
        self.client.force_authenticate(user=self.admin)

    def test_update_user_records_history(self):
        res = self.client.patch(
            f'/api/users/{self.target.pk}/',
            {'first_name': 'New'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.get(
            resource_type=History.ResourceType.USER,
            resource_id=self.target.pk,
            action=History.Action.UPDATE,
        )
        self.assertEqual(entry.changes['fields']['first_name']['old'], 'Old')
        self.assertEqual(entry.changes['fields']['first_name']['new'], 'New')

    def test_user_history_list_endpoint(self):
        History.objects.create(
            account_id=self.account.pk,
            resource_type=History.ResourceType.USER,
            resource_id=self.target.pk,
            entity_type=History.EntityType.USER,
            entity_id=self.target.pk,
            action=History.Action.UPDATE,
            actor=self.admin,
            changes={'fields': {'first_name': {'old': 'A', 'new': 'B'}}},
        )
        res = self.client.get(f'/api/users/{self.target.pk}/history/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
