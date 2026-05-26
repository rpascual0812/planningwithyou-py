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
        response = self.client.get('/api/roles/')
        self.assertEqual(response.status_code, 200)
        names = [row['name'] for row in response.json()]
        self.assertIn('Owner', names)

    def test_create_role_with_read_bookings(self):
        response = self.client.post(
            '/api/roles/',
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
        response = self.client.delete(f'/api/roles/{self.owner.pk}/')
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

        response = self.client.get('/api/roles/feature-catalog/')
        self.assertEqual(response.status_code, 200)
        keys = {row['key'] for row in response.json()}
        self.assertEqual(keys, set(TENANT_FEATURE_KEYS))
        for admin_key in ADMIN_FEATURE_KEYS:
            self.assertNotIn(admin_key, keys)

    def test_feature_catalog_includes_admin_with_admin_read(self):
        from users.test_support import grant_platform_admin

        grant_platform_admin(self.user)

        response = self.client.get('/api/roles/feature-catalog/')
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

        response = self.client.get('/api/users/me/')
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
            title='New',
            description='',
            color='#000',
            sort_order=0,
        )
        response = self.client.post(
            '/api/bookings/items/',
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
            title='Open',
            description='',
            color='#000',
            sort_order=0,
        )

        statuses = self.client.get('/api/booking-statuses/')
        self.assertEqual(statuses.status_code, 200)

        items = self.client.get('/api/bookings/items/')
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
            '/api/booking-statuses/',
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

        response = self.client.get('/api/calendar-statuses/')
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
            '/api/calendar-statuses/',
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

        response = self.client.get('/api/roles/')
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
            '/api/roles/',
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

        response = self.client.get('/api/admin/kyb-verifications/')
        self.assertEqual(response.status_code, 403)

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
            status=CompanyKybVerification.Status.SUBMITTED,
            company_email_domain='acme.com',
            business_description='Test',
        )

        response = self.client.get('/api/admin/kyb-verifications/')
        self.assertEqual(response.status_code, 200)
