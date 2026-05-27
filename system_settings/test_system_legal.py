from django.test import TestCase
from rest_framework.test import APIClient

from system_settings.constants import PRIVACY_POLICY
from system_settings.models import SystemSetting
from users.test_support import assign_owner_role, grant_platform_admin


class SystemLegalAdminApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from users.models import Account, User

        cls.account = Account.objects.create(name='Legal Test Account')
        cls.user = User.objects.create_user(
            username='legaladmin',
            email='legaladmin@example.com',
            password='testpass123',
            account=cls.account,
        )
        assign_owner_role(cls.user)
        grant_platform_admin(cls.user)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_patch_privacy_policy(self):
        row = SystemSetting.objects.get(name=PRIVACY_POLICY)
        res = self.client.patch(
            f'/admin/system-legal/{PRIVACY_POLICY}/',
            {'value': '<p>Privacy text</p>'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.value, '<p>Privacy text</p>')

    def test_public_get_privacy_policy(self):
        SystemSetting.objects.filter(name=PRIVACY_POLICY).update(
            value='<p>Public privacy</p>',
        )
        client = APIClient()
        res = client.get(f'/system-legal/{PRIVACY_POLICY}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['value'], '<p>Public privacy</p>')
