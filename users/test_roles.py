from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from users.models import Account, Role, RolePermission
from users.roles import (
    ADMIN_FEATURE_KEYS,
    FEATURE_KEYS,
    TENANT_FEATURE_KEYS,
    ensure_owner_role,
)

User = get_user_model()


class RoleApiTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create(name='Acme', is_active=True)
        self.company = Company.objects.create(
            account=self.account,
            name='Acme Co',
            is_active=True,
            is_main=True,
            sort_order=0,
        )
        self.owner = ensure_owner_role(self.account)
        self.user = User.objects.create_user(
            username='admin@acme.com',
            email='admin@acme.com',
            password='secret',
            account=self.account,
            company=self.company,
            is_active=True,
            is_verified=True,
            role=self.owner,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_roles_includes_owner(self):
        response = self.client.get('/roles/')
        self.assertEqual(response.status_code, 200)
        names = [row['name'] for row in response.json()]
        self.assertIn('Owner', names)

    def test_create_role_with_read_bookings(self):
        response = self.client.post(
            '/roles/',
            {
                'name': 'Coordinator',
                'is_default': False,
                'permissions': {'bookings': 'read', 'contacts': 'read'},
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        role = Role.objects.get(name='Coordinator', account=self.account)
        self.assertEqual(
            role.permissions.get(feature_key='bookings').access,
            'read',
        )

    def test_cannot_delete_owner_role(self):
        response = self.client.delete(f'/roles/{self.owner.pk}/')
        self.assertEqual(response.status_code, 400)

    def test_feature_catalog_excludes_admin_without_admin_read(self):
        reader = Role.objects.create(account=self.account, name='NoAdmin')
        RolePermission.objects.create(
            role=reader,
            feature_key='roles_permissions',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.get('/roles/feature-catalog/')
        self.assertEqual(response.status_code, 200)
        keys = {row['key'] for row in response.json()}
        self.assertEqual(keys, set(TENANT_FEATURE_KEYS))
        for admin_key in ADMIN_FEATURE_KEYS:
            self.assertNotIn(admin_key, keys)

    def test_feature_catalog_includes_admin_with_admin_read(self):
        from users.test_support import grant_platform_admin

        grant_platform_admin(self.user)

        response = self.client.get('/roles/feature-catalog/')
        self.assertEqual(response.status_code, 200)
        keys = {row['key'] for row in response.json()}
        self.assertEqual(keys, set(TENANT_FEATURE_KEYS) | set(ADMIN_FEATURE_KEYS))

    def test_me_returns_full_permissions_map(self):
        reader = Role.objects.create(
            account=self.account,
            name='Reader',
            is_default=False,
        )
        RolePermission.objects.create(
            role=reader,
            feature_key='bookings',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.get('/users/me/')
        self.assertEqual(response.status_code, 200)
        perms = response.json()['permissions']
        self.assertEqual(perms['bookings'], 'read')
        self.assertEqual(perms['users'], 'none')
        for key in FEATURE_KEYS:
            self.assertIn(key, perms)

    def test_read_only_bookings_cannot_create_booking(self):
        from bookings.models import BookingStatus

        reader = Role.objects.create(account=self.account, name='Reader')
        RolePermission.objects.create(
            role=reader,
            feature_key='bookings',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])
        status = BookingStatus.objects.create(
            account=self.account,
            company=self.company,
            title='New',
            description='',
            color='#000',
            sort_order=0,
        )
        response = self.client.post(
            '/bookings/items/',
            {
                'title': 'Blocked',
                'status': status.pk,
                'notes': '',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_read_bookings_can_get_statuses_and_items(self):
        from bookings.models import BookingStatus

        reader = Role.objects.create(account=self.account, name='Reader')
        RolePermission.objects.create(
            role=reader,
            feature_key='bookings',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])
        BookingStatus.objects.create(
            account=self.account,
            company=self.company,
            title='Open',
            description='',
            color='#000',
            sort_order=0,
        )

        statuses = self.client.get('/booking-statuses/')
        self.assertEqual(statuses.status_code, 200)

        items = self.client.get('/bookings/items/')
        self.assertEqual(items.status_code, 200)

    def test_read_bookings_cannot_post_status(self):
        reader = Role.objects.create(account=self.account, name='Reader')
        RolePermission.objects.create(
            role=reader,
            feature_key='bookings',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.post(
            '/booking-statuses/',
            {'title': 'Blocked', 'description': '', 'color': '#111'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_read_calendar_can_get_calendar_statuses(self):
        reader = Role.objects.create(account=self.account, name='CalReader')
        RolePermission.objects.create(
            role=reader,
            feature_key='calendar',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.get('/calendar-statuses/')
        self.assertEqual(response.status_code, 200)

    def test_read_calendar_cannot_post_calendar_status(self):
        reader = Role.objects.create(account=self.account, name='CalReader')
        RolePermission.objects.create(
            role=reader,
            feature_key='calendar',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.post(
            '/calendar-statuses/',
            {
                'title': 'Blocked',
                'description': '',
                'text_color': '#fff',
                'background_color': '#000',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_roles_permissions_read_can_list_roles(self):
        reader = Role.objects.create(account=self.account, name='RoleReader')
        RolePermission.objects.create(
            role=reader,
            feature_key='roles_permissions',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.get('/roles/')
        self.assertEqual(response.status_code, 200)

    def test_roles_permissions_read_cannot_create_role(self):
        reader = Role.objects.create(account=self.account, name='RoleReader')
        RolePermission.objects.create(
            role=reader,
            feature_key='roles_permissions',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.post(
            '/roles/',
            {
                'name': 'Blocked',
                'is_default': False,
                'permissions': {'bookings': 'read'},
            },
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_platform_admin_read_alone_cannot_list_kyb(self):
        reader = Role.objects.create(account=self.account, name='AdminShell')
        RolePermission.objects.create(
            role=reader,
            feature_key='platform_admin',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.get('/admin/kyb-verifications/')
        self.assertEqual(response.status_code, 403)

    def test_platform_admin_read_alone_cannot_list_accounts(self):
        reader = Role.objects.create(account=self.account, name='AdminShell')
        RolePermission.objects.create(
            role=reader,
            feature_key='platform_admin',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.get('/admin/accounts/')
        self.assertEqual(response.status_code, 403)

    def test_admin_accounts_read_can_list_accounts(self):
        reader = Role.objects.create(account=self.account, name='AccountsReader')
        RolePermission.objects.create(
            role=reader,
            feature_key='admin_accounts',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.get('/admin/accounts/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(row['id'] == self.account.id for row in payload))

    def test_admin_kyb_read_can_list_kyb(self):
        from companies.models import CompanyKybVerification

        reader = Role.objects.create(account=self.account, name='KybReader')
        RolePermission.objects.create(
            role=reader,
            feature_key='admin_company_verification',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])
        CompanyKybVerification.objects.create(
            company=self.company,
            status=CompanyKybVerification.Status.PENDING_PAYMONGO,
            merchant_business_name='Acme Co',
            merchant_email='owner@acme.test',
        )

        response = self.client.get('/admin/kyb-verifications/')
        self.assertEqual(response.status_code, 200)

    def test_change_company_required_to_filter_other_company_users(self):
        other_company = Company.objects.create(
            account=self.account,
            name='Other Co',
            is_active=True,
            is_main=False,
            sort_order=1,
        )
        User.objects.create_user(
            username='other@acme.com',
            email='other@acme.com',
            password='secret',
            account=self.account,
            company=other_company,
            is_active=True,
            is_verified=True,
            role=self.owner,
        )

        reader = Role.objects.create(account=self.account, name='LockedCo')
        RolePermission.objects.create(
            role=reader,
            feature_key='users',
            access='write',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        blocked = self.client.get(f'/users/?company_id={other_company.pk}')
        self.assertEqual(blocked.status_code, 200)
        self.assertEqual(len(blocked.json()), 0)

        RolePermission.objects.create(
            role=reader,
            feature_key='change_company',
            access='read',
        )

        allowed = self.client.get(f'/users/?company_id={other_company.pk}')
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(len(allowed.json()), 1)

    def test_change_company_read_can_fetch_active_companies(self):
        reader = Role.objects.create(account=self.account, name='CoPicker')
        RolePermission.objects.create(
            role=reader,
            feature_key='change_company',
            access='read',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.get('/companies/?active_only=true')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 1)

    def test_change_company_write_can_fetch_active_companies(self):
        reader = Role.objects.create(account=self.account, name='CoPickerWrite')
        RolePermission.objects.create(
            role=reader,
            feature_key='change_company',
            access='write',
        )
        self.user.role = reader
        self.user.save(update_fields=['role_id'])

        response = self.client.get('/companies/?active_only=true')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 1)
