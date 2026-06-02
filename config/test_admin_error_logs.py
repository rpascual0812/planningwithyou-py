from django.utils import timezone
from rest_framework.test import APITestCase

from config.error_logging import log_request_error
from config.models import ErrorLog
from users.models import Role, RolePermission
from users.test_support import assign_owner_role


class AdminErrorLogApiTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from companies.models import Company
        from users.models import Account

        User = get_user_model()
        self.account = Account.objects.create(name='Log Account', is_active=True)
        self.company = Company.objects.create(
            account=self.account,
            name='Log Co',
            is_active=True,
            is_main=True,
        )
        self.user = User.objects.create_user(
            username='logadmin',
            email='logadmin@example.com',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        assign_owner_role(self.user)

    def _grant_error_logs_read(self):
        role = Role.objects.create(account=self.account, name='ErrorLogReader')
        RolePermission.objects.create(
            role=role,
            feature_key='admin_error_logs',
            access='read',
        )
        self.user.role = role
        self.user.save(update_fields=['role_id'])

    def _grant_error_logs_write(self):
        role = Role.objects.create(account=self.account, name='ErrorLogWriter')
        RolePermission.objects.create(
            role=role,
            feature_key='admin_error_logs',
            access='write',
        )
        self.user.role = role
        self.user.save(update_fields=['role_id'])

    def _create_log(self, **kwargs):
        defaults = {
            'method': 'GET',
            'path': '/api/test/',
            'status_code': 500,
            'exception_type': 'RuntimeError',
            'exception_message': 'something broke',
        }
        defaults.update(kwargs)
        return ErrorLog.objects.create(**defaults)

    def test_list_requires_admin_error_logs_permission(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/admin/error-logs/')
        self.assertEqual(response.status_code, 403)

    def test_list_returns_logs_newest_first(self):
        self._grant_error_logs_read()
        self.client.force_authenticate(user=self.user)
        older = self._create_log(exception_message='older error')
        newer = self._create_log(exception_message='newer error')
        ErrorLog.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=1),
        )

        response = self.client.get('/admin/error-logs/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ids = [row['id'] for row in payload['results']]
        self.assertEqual(ids[0], newer.pk)

    def test_list_paginates_ten_per_page(self):
        self._grant_error_logs_read()
        self.client.force_authenticate(user=self.user)
        for i in range(11):
            self._create_log(exception_message=f'error {i}')

        page_one = self.client.get('/admin/error-logs/')
        self.assertEqual(page_one.status_code, 200)
        body_one = page_one.json()
        self.assertEqual(body_one['count'], 11)
        self.assertEqual(len(body_one['results']), 10)
        self.assertIsNotNone(body_one['next'])

        page_two = self.client.get('/admin/error-logs/', {'page': 2})
        self.assertEqual(page_two.status_code, 200)
        body_two = page_two.json()
        self.assertEqual(len(body_two['results']), 1)
        self.assertIsNone(body_two['next'])

    def test_list_filters_by_method_status_date_and_search(self):
        self._grant_error_logs_read()
        self.client.force_authenticate(user=self.user)
        match = self._create_log(
            method='POST',
            status_code=422,
            exception_message='validation failed on field',
        )
        self._create_log(
            method='GET',
            status_code=500,
            exception_message='other',
        )
        today = timezone.localdate().isoformat()
        response = self.client.get(
            '/admin/error-logs/',
            {
                'method': 'post',
                'status_code': '422',
                'occurred_from': today,
                'occurred_to': today,
                'search': 'validation',
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(len(payload['results']), 1)
        self.assertEqual(payload['results'][0]['id'], match.pk)

    def test_resolve_requires_write(self):
        self._grant_error_logs_read()
        self.client.force_authenticate(user=self.user)
        log = self._create_log()
        response = self.client.post(f'/admin/error-logs/{log.pk}/resolve/')
        self.assertEqual(response.status_code, 403)

    def test_resolve_marks_log_resolved(self):
        self._grant_error_logs_write()
        self.client.force_authenticate(user=self.user)
        log = self._create_log()
        response = self.client.post(f'/admin/error-logs/{log.pk}/resolve/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_resolved'])
        log.refresh_from_db()
        self.assertIsNotNone(log.resolved_at)
        self.assertEqual(log.resolved_by_id, self.user.pk)
