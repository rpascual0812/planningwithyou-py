from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account, ImpersonationLog
from users.test_support import assign_owner_role, grant_platform_admin

User = get_user_model()


class ImpersonationTests(TestCase):
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

        self.admin_account = Account.objects.create(
            name='Staff Account',
            country=self.country,
            is_active=True,
        )
        self.admin_company = Company.objects.create(
            account=self.admin_account,
            name='Staff Co',
            supplier_type=self.supplier_type,
            is_main=True,
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            username='admin@test.example',
            email='admin@test.example',
            password=self.password,
            account=self.admin_account,
            company=self.admin_company,
            is_verified=True,
        )
        assign_owner_role(self.admin_user)
        grant_platform_admin(self.admin_user)

        self.tenant_account = Account.objects.create(
            name='Tenant',
            country=self.country,
            is_active=True,
        )
        self.tenant_company = Company.objects.create(
            account=self.tenant_account,
            name='Tenant Co',
            supplier_type=self.supplier_type,
            is_main=True,
            is_active=True,
        )
        self.target_user = User.objects.create_user(
            username='tenant@test.example',
            email='tenant@test.example',
            password=self.password,
            account=self.tenant_account,
            company=self.tenant_company,
            is_verified=True,
        )
        assign_owner_role(self.target_user)

    def _login(self, user):
        return self.client.post(
            '/token/',
            {'email': user.email, 'password': self.password},
            format='json',
        )

    def test_impersonation_does_not_bump_target_token_version(self):
        self._login(self.admin_user)
        before_version = self.target_user.token_version

        response = self.client.post(
            '/admin/impersonate/',
            {'user_id': self.target_user.pk},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.token_version, before_version)

        log = ImpersonationLog.objects.get(pk=response.data['impersonation_log_id'])
        self.assertEqual(log.admin_user_id, self.admin_user.pk)
        self.assertEqual(log.target_user_id, self.target_user.pk)
        self.assertIsNone(log.ended_at)

    def test_impersonation_me_and_admin_block(self):
        self._login(self.admin_user)
        start = self.client.post(
            '/admin/impersonate/',
            {'user_id': self.target_user.pk},
            format='json',
        )
        self.assertEqual(start.status_code, 200)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {start.data["access"]}')
        me = self.client.get('/users/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data['id'], self.target_user.pk)
        self.assertTrue(me.data['impersonating'])

        admin_accounts = self.client.get('/admin/accounts/')
        self.assertEqual(admin_accounts.status_code, 403)

    def test_end_impersonation_closes_log(self):
        self._login(self.admin_user)
        start = self.client.post(
            '/admin/impersonate/',
            {'user_id': self.target_user.pk},
            format='json',
        )
        log_id = start.data['impersonation_log_id']
        refresh = start.data['refresh']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {start.data["access"]}')
        end = self.client.post(
            '/admin/impersonate/end/',
            {'refresh': refresh},
            format='json',
        )
        self.assertEqual(end.status_code, 200)

        log = ImpersonationLog.objects.get(pk=log_id)
        self.assertIsNotNone(log.ended_at)

        refresh_res = self.client.post(
            '/token/refresh/',
            {'refresh': refresh},
            format='json',
        )
        self.assertEqual(refresh_res.status_code, 401)

    def test_target_session_survives_impersonation(self):
        target_login = self._login(self.target_user)
        target_access = target_login.data['access']
        target_version = self.target_user.token_version

        self._login(self.admin_user)
        start = self.client.post(
            '/admin/impersonate/',
            {'user_id': self.target_user.pk},
            format='json',
        )
        self.assertEqual(start.status_code, 200)

        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.token_version, target_version)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {target_access}')
        me = self.client.get('/users/me/')
        self.assertEqual(me.status_code, 200)

    def test_impersonation_scopes_to_target_company(self):
        from contacts.models import Contact

        other_company = Company.objects.create(
            account=self.tenant_account,
            name='Other Co',
            supplier_type=self.supplier_type,
            is_main=False,
            is_active=True,
        )
        Contact.objects.create(
            account=self.tenant_account,
            company_org=self.tenant_company,
            first_name='Alice',
            last_name='One',
            email='alice@tenant.example',
        )
        Contact.objects.create(
            account=self.tenant_account,
            company_org=other_company,
            first_name='Bob',
            last_name='Two',
            email='bob@tenant.example',
        )

        self._login(self.admin_user)
        start = self.client.post(
            '/admin/impersonate/',
            {'user_id': self.target_user.pk},
            format='json',
        )
        self.assertEqual(start.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {start.data["access"]}')

        contacts = self.client.get('/contacts/')
        self.assertEqual(contacts.status_code, 200)
        emails = {row['email'] for row in contacts.data}
        self.assertIn('alice@tenant.example', emails)
        self.assertNotIn('bob@tenant.example', emails)

        contacts_other = self.client.get(f'/contacts/?company_id={other_company.pk}')
        self.assertEqual(contacts_other.status_code, 200)
        emails_other = {row['email'] for row in contacts_other.data}
        self.assertNotIn('bob@tenant.example', emails_other)

        companies = self.client.get('/companies/?active_only=true')
        self.assertEqual(companies.status_code, 200)
        self.assertEqual(len(companies.data), 1)
        self.assertEqual(companies.data[0]['id'], self.tenant_company.pk)

        dashboard = self.client.get('/dashboard/summary/')
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(len(dashboard.data['companies']), 1)
        self.assertEqual(dashboard.data['companies'][0]['id'], self.tenant_company.pk)
