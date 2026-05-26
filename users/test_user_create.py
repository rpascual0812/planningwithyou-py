from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from subscriptions.models import AccountSubscription, Subscription
from suppliers.models import SupplierType
from users.models import Account
from users.test_support import assign_owner_role

User = get_user_model()


class UserCreateSubscriptionTests(TestCase):
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
        cls.free_sub = Subscription.objects.create(
            plan='free',
            name='Free',
            billing_cycle='monthly',
            base_price=0,
            price_per_user=0,
        )
        cls.paid_sub = Subscription.objects.create(
            plan='starter',
            name='Starter',
            billing_cycle='monthly',
            base_price=100,
            price_per_user=10,
        )

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
        self.client.force_authenticate(user=self.admin)

    def _create_payload(self):
        return {
            'username': 'newuser',
            'email': 'newuser@test.example',
            'first_name': 'New',
            'last_name': 'User',
            'is_active': True,
        }

    @patch('users.views._send_reset_email')
    def test_create_user_forbidden_on_free_plan(self, _mock_email):
        AccountSubscription.objects.create(
            account=self.account,
            subscription=self.free_sub,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=1,
            start_date=date.today(),
            base_price=0,
            total_price=0,
        )
        response = self.client.post('/api/users/', self._create_payload(), format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            User.objects.filter(email='newuser@test.example').exists(),
        )

    @patch('users.views._send_reset_email')
    def test_create_user_allowed_on_paid_plan(self, _mock_email):
        AccountSubscription.objects.create(
            account=self.account,
            subscription=self.paid_sub,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=1,
            start_date=date.today(),
            base_price=100,
            total_price=100,
        )
        response = self.client.post('/api/users/', self._create_payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            User.objects.filter(email='newuser@test.example').exists(),
        )
