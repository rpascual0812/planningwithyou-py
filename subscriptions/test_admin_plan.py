from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from subscriptions.models import AccountSubscription, Subscription
from suppliers.models import SupplierType
from users.roles import ensure_owner_role
from users.models import Account

from users.test_support import grant_platform_admin

User = get_user_model()


def _ensure_account_id_sequence() -> None:
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence('accounts','id'), "
            "COALESCE((SELECT MAX(id) FROM accounts), 1))"
        )


class AdminSubscriptionPlanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.free_monthly = Subscription.objects.filter(
            plan='free',
            billing_cycle='monthly',
        ).first()
        cls.admin_monthly = Subscription.objects.filter(
            plan='admin',
            billing_cycle='monthly',
        ).first()
        cls.pro_monthly = Subscription.objects.filter(
            plan='pro',
            billing_cycle='monthly',
        ).first()
        if (
            cls.free_monthly is None
            or cls.admin_monthly is None
            or cls.pro_monthly is None
        ):
            cls.skip_setup = True
            return
        cls.skip_setup = False

    def setUp(self):
        if getattr(self, 'skip_setup', True):
            self.skipTest('Subscription seed data missing')
        self.client = APIClient()
        _ensure_account_id_sequence()
        self.country, _ = Country.objects.get_or_create(
            iso_code='PHL',
            defaults={
                'name': 'Philippines',
                'iso2_code': 'PH',
                'currency': 'Peso',
                'currency_symbol': '₱',
                'currency_code': 'PHP',
            },
        )
        self.account = Account.objects.create(
            name='Test Account',
            is_active=True,
            country=self.country,
        )
        self.supplier_type, _ = SupplierType.objects.get_or_create(name='Planner')
        self.company = Company.objects.create(
            account=self.account,
            name='Test Co',
            is_active=True,
            is_main=True,
            supplier_type=self.supplier_type,
        )
        owner = ensure_owner_role(self.account)
        self.user = User.objects.create_user(
            username='owner@test.example',
            email='owner@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
            role=owner,
        )
        self.client.force_authenticate(user=self.user)

    def test_admin_plan_hidden_from_regular_users(self):
        res = self.client.get('/subscriptions/?billing_cycle=monthly')
        self.assertEqual(res.status_code, 200)
        plans = {row['plan'] for row in res.data}
        self.assertNotIn('admin', plans)

    def test_admin_plan_visible_to_platform_admin(self):
        grant_platform_admin(self.user)
        res = self.client.get('/subscriptions/?billing_cycle=monthly')
        self.assertEqual(res.status_code, 200)
        plans = {row['plan'] for row in res.data}
        self.assertIn('admin', plans)
        admin_row = next(row for row in res.data if row['plan'] == 'admin')
        self.assertEqual(admin_row['name'], 'Admin')

    def test_subscribe_admin_requires_platform_admin(self):
        res = self.client.post(
            '/subscriptions/subscribe-admin/',
            {'billing_cycle': 'monthly', 'team_seats': 2},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('not available', res.data['detail'].lower())

    def test_platform_admin_can_activate_admin_plan(self):
        grant_platform_admin(self.user)
        res = self.client.post(
            '/subscriptions/subscribe-admin/',
            {'billing_cycle': 'monthly', 'team_seats': 3},
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['plan'], 'admin')
        self.assertEqual(res.data['team_seats'], 3)

        row = AccountSubscription.objects.get(account=self.account, deleted_at__isnull=True)
        self.assertEqual(row.subscription.plan, 'admin')
        self.assertEqual(row.team_seats, 3)
        self.assertEqual(row.total_price, Decimal('0.00'))
