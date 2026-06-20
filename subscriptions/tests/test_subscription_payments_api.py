from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from subscriptions.models import (
    AccountSubscription,
    Subscription,
    SubscriptionPayment,
    SubscriptionReceipt,
)
from users.models import Account
from users.test_support import assign_owner_role

User = get_user_model()


class SubscriptionPaymentsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pro_monthly = Subscription.objects.filter(
            plan='pro',
            billing_cycle='monthly',
        ).first()
        if cls.pro_monthly is None:
            cls.skip_setup = True
            return
        cls.skip_setup = False

    def setUp(self):
        if getattr(self, 'skip_setup', True):
            self.skipTest('Subscription seed data missing')
        self.client = APIClient()
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
            name='Receipt Co',
            country=self.country,
            is_active=True,
            contact_email='billing@receipt.test',
        )
        self.company = Company.objects.create(
            account=self.account,
            name='Receipt Co',
            is_active=True,
            is_main=True,
        )
        self.user = User.objects.create_user(
            username='billing@receipt.test',
            email='billing@receipt.test',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        assign_owner_role(self.user)
        self.account_sub = AccountSubscription.objects.create(
            account=self.account,
            subscription=self.pro_monthly,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=1,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            base_price=Decimal('995'),
            total_per_users=Decimal('0'),
            total_price=Decimal('995'),
        )
        self.payment = SubscriptionPayment.objects.create(
            account=self.account,
            account_subscription=self.account_sub,
            amount=Decimal('995.00'),
            paid_at=timezone.now(),
            period_start=timezone.localdate(),
            period_end=timezone.localdate(),
            description='Pro subscription renewal',
        )
        self.receipt = SubscriptionReceipt.objects.create(
            account=self.account,
            payment=self.payment,
            receipt_number=f'SPR-{self.payment.pk}',
        )
        self.client.force_authenticate(user=self.user)

    def test_list_subscription_payments_for_account(self):
        res = self.client.get(reverse('subscription-payment-list'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        row = res.data[0]
        self.assertEqual(row['id'], self.payment.pk)
        self.assertEqual(row['plan_name'], self.pro_monthly.name)
        self.assertEqual(row['receipt']['receipt_number'], self.receipt.receipt_number)
