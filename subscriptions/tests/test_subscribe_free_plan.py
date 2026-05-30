from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from companies.models import Company
from subscriptions.models import AccountSubscription, Subscription
from users.models import Account
from users.roles import ensure_owner_role

User = get_user_model()


class SubscribeFreePlanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.free_monthly = Subscription.objects.filter(
            plan='free',
            billing_cycle='monthly',
        ).first()
        cls.pro_monthly = Subscription.objects.filter(
            plan='pro',
            billing_cycle='monthly',
        ).first()
        if cls.free_monthly is None or cls.pro_monthly is None:
            cls.skip_setup = True
            return
        cls.skip_setup = False

    def setUp(self):
        if getattr(self, 'skip_setup', True):
            self.skipTest('Subscription seed data missing')
        self.client = APIClient()
        self.account = Account.objects.create(name='Test Account', is_active=True)
        self.company = Company.objects.create(
            account=self.account,
            name='Test Co',
            is_active=True,
            is_main=True,
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

    def test_subscribe_free_schedules_downgrade_while_prepaid_active(self):
        today = timezone.localdate()
        paid = AccountSubscription.objects.create(
            account=self.account,
            subscription=self.pro_monthly,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=2,
            start_date=today,
            end_date=today + timedelta(days=30),
            base_price=Decimal('995'),
            total_per_users=Decimal('100'),
            total_price=Decimal('1095'),
            reference_id='subs_test_paid',
        )
        res = self.client.post(
            '/subscriptions/subscribe-free/',
            {'billing_cycle': 'monthly'},
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['plan'], 'pro')
        self.assertEqual(res.data['scheduled_plan'], 'free')

        paid.refresh_from_db()
        self.assertEqual(paid.status, AccountSubscription.Status.ACTIVE)
        self.assertEqual(paid.subscription.plan, 'pro')
        self.assertEqual(paid.scheduled_subscription.plan, 'free')

    def test_subscribe_free_rejects_when_already_free(self):
        AccountSubscription.objects.create(
            account=self.account,
            subscription=self.free_monthly,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=1,
            start_date=timezone.localdate(),
            end_date=None,
            base_price=Decimal('0'),
            total_per_users=Decimal('0'),
            total_price=Decimal('0'),
        )
        res = self.client.post(
            '/subscriptions/subscribe-free/',
            {'billing_cycle': 'monthly'},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
