from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class SingleSessionTests(TestCase):
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
            username='single@test.example',
            email='single@test.example',
            password=self.password,
            account=self.account,
            company=self.company,
            is_verified=True,
        )

    def _login(self):
        return self.client.post(
            '/api/token/',
            {
                'email': self.user.email,
                'password': self.password,
            },
            format='json',
        )

    def test_second_login_invalidates_first_session_tokens(self):
        first = self._login()
        self.assertEqual(first.status_code, 200)
        first_access = first.data['access']
        first_refresh = first.data['refresh']

        second = self._login()
        self.assertEqual(second.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.token_version, 2)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {first_access}')
        me = self.client.get('/api/users/me/')
        self.assertEqual(me.status_code, 401)

        refresh_res = self.client.post(
            '/api/token/refresh/',
            {'refresh': first_refresh},
            format='json',
        )
        self.assertEqual(refresh_res.status_code, 401)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {second.data["access"]}')
        me_ok = self.client.get('/api/users/me/')
        self.assertEqual(me_ok.status_code, 200)
