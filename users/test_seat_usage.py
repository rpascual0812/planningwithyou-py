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


class UserSeatUsageTests(TestCase):
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
        cls.paid_sub = Subscription.objects.create(
            plan='starter',
            name='Starter',
            billing_cycle='monthly',
            base_price=100,
            price_per_user=10,
            default_users=1,
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
        AccountSubscription.objects.create(
            account=self.account,
            subscription=self.paid_sub,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=2,
            start_date=date.today(),
            base_price=100,
            total_price=100,
        )
        self.client.force_authenticate(user=self.admin)

    def test_seat_usage_counts_active_users_across_account(self):
        User.objects.create_user(
            username='extra',
            email='extra@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_active=True,
            is_verified=True,
        )
        res = self.client.get('/api/users/seat-usage/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['active_users_count'], 2)
        self.assertEqual(res.data['team_seats'], 2)
        self.assertTrue(res.data['at_seat_limit'])

    @patch('users.views._send_reset_email')
    def test_create_user_blocked_at_seat_limit(self, _mock_email):
        User.objects.create_user(
            username='filled',
            email='filled@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_active=True,
            is_verified=True,
        )
        payload = {
            'username': 'newuser',
            'email': 'newuser@test.example',
            'first_name': 'New',
            'last_name': 'User',
            'is_active': True,
        }
        res = self.client.post('/api/users/', payload, format='json')
        self.assertEqual(res.status_code, 403)

    def test_activate_user_blocked_at_seat_limit(self):
        inactive = User.objects.create_user(
            username='inactive',
            email='inactive@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_active=False,
            is_verified=True,
        )
        User.objects.create_user(
            username='filled',
            email='filled@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_active=True,
            is_verified=True,
        )
        res = self.client.patch(
            f'/api/users/{inactive.id}/',
            {'is_active': True},
            format='json',
        )
        self.assertEqual(res.status_code, 403)
        inactive.refresh_from_db()
        self.assertFalse(inactive.is_active)
