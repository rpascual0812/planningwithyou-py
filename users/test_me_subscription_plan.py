from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from subscriptions.models import AccountSubscription, Subscription
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class MeSubscriptionPlanTests(TestCase):
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
        cls.starter = Subscription.objects.create(
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
        self.user = User.objects.create_user(
            username='me@test.example',
            email='me@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_me_returns_free_when_no_account_subscription(self):
        res = self.client.get('/api/users/me/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['subscription_plan'], 'free')

    def test_me_returns_subscriptions_plan_via_account_subscriptions(self):
        AccountSubscription.objects.create(
            account=self.account,
            subscription=self.starter,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=1,
            start_date=date.today(),
            base_price=100,
            total_price=100,
        )
        res = self.client.get('/api/users/me/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['subscription_plan'], 'starter')
