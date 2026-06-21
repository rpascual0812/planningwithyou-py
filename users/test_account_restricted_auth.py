from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.jwt import ACCOUNT_RESTRICTED_CODE, ACCOUNT_RESTRICTED_MESSAGE
from users.models import Account

User = get_user_model()


class AccountRestrictedAuthTests(TestCase):
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
            username='restricted-auth@test.example',
            email='restricted-auth@test.example',
            password=self.password,
            account=self.account,
            company=self.company,
            is_verified=True,
        )

    def _token_payload(self):
        return {
            'username': self.user.email,
            'email': self.user.email,
            'password': self.password,
        }

    def _login(self):
        return self.client.post('/token/', self._token_payload(), format='json')

    def test_login_fails_when_account_restricted(self):
        self.user.account_restricted = True
        self.user.save(update_fields=['account_restricted'])

        res = self.client.post('/token/', self._token_payload(), format='json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data['code'], ACCOUNT_RESTRICTED_CODE)
        self.assertEqual(res.data['detail'], ACCOUNT_RESTRICTED_MESSAGE)

    def test_restricting_user_invalidates_existing_session(self):
        login = self._login()
        self.assertEqual(login.status_code, 200)
        access = login.data['access']

        self.user.account_restricted = True
        self.user.save(update_fields=['account_restricted'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.token_version, 1)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        me = self.client.get('/users/me/')
        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.data['code'], ACCOUNT_RESTRICTED_CODE)
