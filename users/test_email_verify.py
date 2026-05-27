from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from subscriptions.models import Subscription
from users.models import Account, EmailVerificationToken

User = get_user_model()


class EmailVerifyApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Subscription.objects.create(
            plan='free',
            name='Free',
            billing_cycle='monthly',
            base_price=0,
            price_per_user=0,
        )
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
            username='verify@test.example',
            email='verify@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=False,
        )
        self.verification = EmailVerificationToken.objects.create(user=self.user)

    def test_verify_email_issues_tokens_and_sets_is_verified(self):
        res = self.client.post(
            '/verify-email/',
            {'token': str(self.verification.token)},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        self.verification.refresh_from_db()
        self.assertTrue(self.verification.used)

    def test_login_blocked_until_verified(self):
        res = self.client.post(
            '/token/',
            {
                'username': self.user.email,
                'email': self.user.email,
                'password': 'secret12',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 401)
        self.assertIn('verify', res.data['detail'].lower())

    @patch('users.views.send_email_task.delay')
    def test_register_does_not_return_jwt(self, _mock_delay):
        res = self.client.post(
            '/register/',
            {
                'company_name': 'New Co',
                'supplier_type_id': self.supplier_type.id,
                'first_name': 'Ann',
                'last_name': 'Bee',
                'email': 'ann@newco.test',
                'mobile_number': '+639171234567',
                'password': 'secret12',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertNotIn('access', res.data)
        user = User.objects.get(email='ann@newco.test')
        self.assertFalse(user.is_verified)
