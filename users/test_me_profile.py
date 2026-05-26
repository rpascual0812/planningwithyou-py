from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from users.models import Account, Role, RolePermission
from users.roles import ensure_owner_role

User = get_user_model()


class MeProfileUpdateTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create(name='Acme', is_active=True)
        self.company = Company.objects.create(
            account=self.account,
            name='Acme Co',
            is_active=True,
            is_main=True,
            sort_order=0,
        )
        owner = ensure_owner_role(self.account)
        limited = Role.objects.create(account=self.account, name='Viewer')
        RolePermission.objects.update_or_create(
            role=limited,
            feature_key='users',
            defaults={'access': 'read'},
        )
        RolePermission.objects.update_or_create(
            role=limited,
            feature_key='bookings',
            defaults={'access': 'read'},
        )

        self.limited_user = User.objects.create_user(
            username='viewer@acme.com',
            email='viewer@acme.com',
            password='secret',
            account=self.account,
            company=self.company,
            is_active=True,
            is_verified=True,
            role=limited,
            first_name='View',
            last_name='Only',
        )
        self.admin = User.objects.create_user(
            username='owner@acme.com',
            email='owner@acme.com',
            password='secret',
            account=self.account,
            company=self.company,
            is_active=True,
            is_verified=True,
            role=owner,
        )
        self.client = APIClient()

    def test_limited_user_can_patch_own_profile_via_me(self):
        self.client.force_authenticate(user=self.limited_user)
        response = self.client.patch(
            '/api/users/me/',
            {'first_name': 'Updated'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.limited_user.refresh_from_db()
        self.assertEqual(self.limited_user.first_name, 'Updated')

    def test_limited_user_cannot_patch_other_users(self):
        self.client.force_authenticate(user=self.limited_user)
        response = self.client.patch(
            f'/api/users/{self.admin.pk}/',
            {'first_name': 'Hacked'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)
