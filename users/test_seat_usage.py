from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from subscriptions.models import AccountSubscription, Subscription
from suppliers.models import SupplierType
from users.models import Account
from users.test_support import assign_owner_role

User = get_user_model()


def _ensure_account_id_sequence() -> None:
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence('accounts','id'), "
            "COALESCE((SELECT MAX(id) FROM accounts), 1))"
        )


class UserSeatUsageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country, _ = Country.objects.get_or_create(
            iso_code='PHL',
            defaults={
                'name': 'Philippines',
                'iso2_code': 'PH',
                'currency': 'Peso',
                'currency_symbol': '₱',
                'currency_code': 'PHP',
            },
        )
        cls.supplier_type, _ = SupplierType.objects.get_or_create(name='Planner')
        cls.paid_sub = Subscription.objects.create(
            plan='starter',
            name='Starter',
            billing_cycle='monthly',
            base_price=100,
            price_per_user=10,
            default_users=1,
        )
        cls.free_sub = Subscription.objects.filter(
            plan='free',
            billing_cycle='monthly',
        ).first()

    def setUp(self):
        self.client = APIClient()
        _ensure_account_id_sequence()
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
        res = self.client.get('/users/seat-usage/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['active_users_count'], 2)
        self.assertEqual(res.data['team_seats'], 3)
        self.assertFalse(res.data['at_seat_limit'])

    @patch('users.views._send_reset_email')
    def test_create_user_blocked_at_seat_limit(self, _mock_email):
        User.objects.create_user(
            username='filled1',
            email='filled1@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_active=True,
            is_verified=True,
        )
        User.objects.create_user(
            username='filled2',
            email='filled2@test.example',
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
        res = self.client.post('/users/', payload, format='json')
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
            username='filled1',
            email='filled1@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_active=True,
            is_verified=True,
        )
        User.objects.create_user(
            username='filled2',
            email='filled2@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_active=True,
            is_verified=True,
        )
        res = self.client.patch(
            f'/users/{inactive.id}/',
            {'is_active': True},
            format='json',
        )
        self.assertEqual(res.status_code, 403)
        inactive.refresh_from_db()
        self.assertFalse(inactive.is_active)

    def test_free_plan_allows_only_one_user(self):
        if self.free_sub is None:
            self.skipTest('Free subscription seed data missing')
        AccountSubscription.objects.filter(account=self.account).delete()
        AccountSubscription.objects.create(
            account=self.account,
            subscription=self.free_sub,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=2,
            start_date=date.today(),
            end_date=None,
            base_price=0,
            total_price=0,
        )
        res = self.client.get('/users/seat-usage/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['team_seats'], 1)
        self.assertTrue(res.data['at_seat_limit'])

    def test_free_plan_blocks_activating_second_user(self):
        if self.free_sub is None:
            self.skipTest('Free subscription seed data missing')
        AccountSubscription.objects.filter(account=self.account).delete()
        AccountSubscription.objects.create(
            account=self.account,
            subscription=self.free_sub,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=2,
            start_date=date.today(),
            end_date=None,
            base_price=0,
            total_price=0,
        )
        inactive = User.objects.create_user(
            username='inactive-free',
            email='inactive-free@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_active=False,
            is_verified=True,
        )
        res = self.client.patch(
            f'/users/{inactive.id}/',
            {'is_active': True},
            format='json',
        )
        self.assertEqual(res.status_code, 403)
        inactive.refresh_from_db()
        self.assertFalse(inactive.is_active)


class AccountRestrictedUserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country, _ = Country.objects.get_or_create(
            iso_code='PHL',
            defaults={
                'name': 'Philippines',
                'iso2_code': 'PH',
                'currency': 'Peso',
                'currency_symbol': '₱',
                'currency_code': 'PHP',
            },
        )
        cls.supplier_type, _ = SupplierType.objects.get_or_create(name='Planner')

    def setUp(self):
        self.client = APIClient()
        _ensure_account_id_sequence()
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
        self.restricted = User.objects.create_user(
            username='restricted@test.example',
            email='restricted@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
            account_restricted=True,
        )
        self.client.force_authenticate(user=self.admin)

    def test_update_blocked_for_account_restricted_user(self):
        res = self.client.patch(
            f'/users/{self.restricted.id}/',
            {'first_name': 'Blocked'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)
        self.restricted.refresh_from_db()
        self.assertNotEqual(self.restricted.first_name, 'Blocked')

    def test_delete_blocked_for_account_restricted_user(self):
        res = self.client.delete(f'/users/{self.restricted.id}/')
        self.assertEqual(res.status_code, 403)
        self.restricted.refresh_from_db()
        self.assertIsNone(self.restricted.deleted_at)
