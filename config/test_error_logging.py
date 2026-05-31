from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from companies.models import Company
from config.drf_exception_handler import custom_exception_handler
from config.error_logging import log_request_error
from config.middleware import ErrorLoggingMiddleware
from config.models import ErrorLog
from users.models import Account
from users.roles import ensure_owner_role

User = get_user_model()


class ErrorLoggingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.account = Account.objects.create(name='Err Account', is_active=True)
        self.company = Company.objects.create(
            account=self.account,
            name='Err Co',
            is_active=True,
            is_main=True,
        )
        owner = ensure_owner_role(self.account)
        self.user = User.objects.create_user(
            username='erruser',
            email='err@example.com',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
            role=owner,
        )

    def test_log_request_error_persists_row(self):
        request = self.factory.post('/api/bookings/', data='{"title":"x"}', content_type='application/json')
        request.user = self.user

        log_request_error(request, exception=RuntimeError('boom'), status_code=500)

        log = ErrorLog.objects.get()
        self.assertEqual(log.method, 'POST')
        self.assertEqual(log.path, '/api/bookings/')
        self.assertEqual(log.status_code, 500)
        self.assertEqual(log.exception_type, 'RuntimeError')
        self.assertIn('boom', log.exception_message)
        self.assertIn('RuntimeError', log.traceback)
        self.assertEqual(log.user_id, self.user.pk)
        self.assertEqual(log.account_id, self.account.pk)

    def test_log_request_error_redacts_sensitive_paths(self):
        request = self.factory.post(
            '/users/login/',
            data='{"password":"secret"}',
            content_type='application/json',
        )
        request.user = self.user

        log_request_error(request, exception=ValueError('bad login'), status_code=400)

        log = ErrorLog.objects.get()
        self.assertEqual(log.request_body, '')

    def test_middleware_logs_unhandled_exception(self):
        request = self.factory.get('/broken/')
        request.user = self.user
        middleware = ErrorLoggingMiddleware(lambda req: (_ for _ in ()).throw(ValueError('view failed')))

        with self.assertRaises(ValueError):
            middleware(request)

        log = ErrorLog.objects.get()
        self.assertEqual(log.exception_type, 'ValueError')
        self.assertEqual(log.status_code, 500)

    def test_exception_handler_is_configured_globally(self):
        from django.conf import settings

        self.assertEqual(
            settings.REST_FRAMEWORK['EXCEPTION_HANDLER'],
            'config.drf_exception_handler.custom_exception_handler',
        )

    def test_error_logging_middleware_is_outermost(self):
        from django.conf import settings

        self.assertEqual(
            settings.MIDDLEWARE[0],
            'config.middleware.ErrorLoggingMiddleware',
        )

    def test_drf_exception_handler_logs_unhandled_api_error(self):
        request = APIRequestFactory().get('/users/me/')
        request.user = self.user

        custom_exception_handler(RuntimeError('api boom'), {'request': request, 'view': None})

        log = ErrorLog.objects.get()
        self.assertEqual(log.exception_type, 'RuntimeError')
        self.assertEqual(log.status_code, 500)

    def test_drf_exception_handler_skips_client_errors(self):
        from rest_framework.exceptions import ValidationError

        request = APIRequestFactory().post('/users/me/', {}, format='json')
        request.user = self.user

        response = custom_exception_handler(
            ValidationError({'email': ['invalid']}),
            {'request': request, 'view': None},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ErrorLog.objects.count(), 0)
