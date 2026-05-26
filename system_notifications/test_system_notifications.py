from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from system_notifications.models import SystemNotification
from users.models import Account, User


class SystemNotificationApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company='Test Co')
        cls.admin = User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='test-pass',
            account=cls.account,
            is_admin=True,
        )
        cls.user = User.objects.create_user(
            username='user@example.com',
            email='user@example.com',
            password='test-pass',
            account=cls.account,
            is_admin=False,
        )
        cls.now = timezone.now()

    def setUp(self):
        self.client = APIClient()

    def _login(self, user: User):
        self.client.force_authenticate(user=user)

    def test_active_notifications_for_current_window(self):
        SystemNotification.objects.create(
            title='Active',
            message='Hello team',
            start_date=self.now - timedelta(hours=1),
            end_date=self.now + timedelta(days=7),
            created_by=self.admin,
        )
        SystemNotification.objects.create(
            title='Future',
            message='Later',
            start_date=self.now + timedelta(days=1),
            end_date=self.now + timedelta(days=7),
            created_by=self.admin,
        )
        self._login(self.user)
        res = self.client.get('/api/system-notifications/active/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]['title'], 'Active')

    def test_admin_crud_and_soft_delete(self):
        self._login(self.admin)
        start = self.now
        end = self.now + timedelta(days=1)
        create = self.client.post(
            '/api/admin/system-notifications/',
            {
                'title': 'Maintenance',
                'message': 'Tonight 10pm',
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
            },
            format='json',
        )
        self.assertEqual(create.status_code, 201)
        row_id = create.json()['id']
        self.assertEqual(create.json()['created_by'], self.admin.pk)

        delete = self.client.delete(f'/api/admin/system-notifications/{row_id}/')
        self.assertEqual(delete.status_code, 204)
        row = SystemNotification.all_objects.get(pk=row_id)
        self.assertIsNotNone(row.deleted_at)

        self._login(self.user)
        active = self.client.get('/api/system-notifications/active/')
        self.assertEqual(len(active.json()), 0)

    def test_non_admin_cannot_manage(self):
        self._login(self.user)
        res = self.client.post(
            '/api/admin/system-notifications/',
            {
                'title': 'Nope',
                'message': 'Denied',
                'start_date': self.now.isoformat(),
                'end_date': (self.now + timedelta(hours=1)).isoformat(),
            },
            format='json',
        )
        self.assertEqual(res.status_code, 403)
