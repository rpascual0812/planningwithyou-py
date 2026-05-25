from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class LoginTokenApiTests(TestCase):
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
        cls.password = 'secret12'

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
            username='login@test.example',
            email='login@test.example',
            password=self.password,
            account=self.account,
            company=self.company,
        )

    def _token_payload(self):
        return {
            'username': self.user.email,
            'email': self.user.email,
            'password': self.password,
        }

    def test_login_succeeds_when_account_and_company_active(self):
        res = self.client.post('/api/token/', self._token_payload(), format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.data)

    def test_login_fails_when_account_inactive(self):
        self.account.is_active = False
        self.account.save(update_fields=['is_active'])
        res = self.client.post('/api/token/', self._token_payload(), format='json')
        self.assertEqual(res.status_code, 401)

    def test_login_fails_when_company_inactive(self):
        self.company.is_active = False
        self.company.save(update_fields=['is_active'])
        res = self.client.post('/api/token/', self._token_payload(), format='json')
        self.assertEqual(res.status_code, 401)

    def test_login_fails_when_user_inactive(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        res = self.client.post('/api/token/', self._token_payload(), format='json')
        self.assertEqual(res.status_code, 401)
