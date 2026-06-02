from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account
from users.test_support import assign_owner_role

User = get_user_model()


class UsersCompanyFilterTests(TestCase):
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

    def setUp(self):
        self.client = APIClient()
        self.account = Account.objects.create(
            name='Tenant',
            country=self.country,
            is_active=True,
        )
        self.company_a = Company.objects.create(
            account=self.account,
            name='Company A',
            supplier_type=self.supplier_type,
            is_main=True,
            is_active=True,
        )
        self.company_b = Company.objects.create(
            account=self.account,
            name='Company B',
            supplier_type=self.supplier_type,
            is_main=False,
            is_active=True,
        )
        self.admin = User.objects.create_user(
            username='admin@test.example',
            email='admin@test.example',
            password='secret12',
            account=self.account,
            company=self.company_a,
            is_verified=True,
        )
        assign_owner_role(self.admin)
        self.user_a = User.objects.create_user(
            username='usera',
            email='usera@test.example',
            password='secret12',
            account=self.account,
            company=self.company_a,
            is_verified=True,
        )
        self.user_b = User.objects.create_user(
            username='userb',
            email='userb@test.example',
            password='secret12',
            account=self.account,
            company=self.company_b,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.admin)

    def test_list_users_filtered_by_company_id(self):
        res = self.client.get(f'/users/?company_id={self.company_b.id}')
        self.assertEqual(res.status_code, 200)
        emails = {row['email'] for row in res.data['results']}
        self.assertEqual(emails, {'userb@test.example'})

    def test_non_admin_cannot_list_other_company(self):
        self.client.force_authenticate(
            user=User.objects.get(email='usera@test.example'),
        )
        res = self.client.get(f'/users/?company_id={self.company_b.id}')
        self.assertEqual(res.status_code, 200)
        emails = {row['email'] for row in res.data['results']}
        self.assertEqual(emails, {'usera@test.example'})

    def test_users_list_is_paginated(self):
        for i in range(12):
            User.objects.create_user(
                username=f'extra{i}@test.example',
                email=f'extra{i}@test.example',
                password='secret12',
                account=self.account,
                company=self.company_a,
                is_verified=True,
            )
        res = self.client.get('/users/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('count', res.data)
        self.assertIn('results', res.data)
        self.assertEqual(len(res.data['results']), 10)
        self.assertIsNotNone(res.data['next'])
