from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from config.models import ErrorLog
from emails.gmail_service import (
    GmailOAuthError,
    _exchange_oauth_code,
    google_oauth_configured,
    integration_status_payload,
)
from emails.models import GmailIntegration


class GmailOAuthCallbackErrorLoggingTests(TestCase):
    @override_settings(FRONTEND_URL='https://app.example.com')
    def test_google_error_query_param_is_logged(self):
        client = APIClient()
        res = client.get('/email-integrations/gmail/oauth/callback/?error=access_denied')
        self.assertEqual(res.status_code, 302)
        log = ErrorLog.objects.get()
        self.assertEqual(log.path, '/email-integrations/gmail/oauth/callback/')
        self.assertEqual(log.status_code, 400)
        self.assertEqual(log.exception_type, 'GmailOAuthError')
        self.assertIn('access_denied', log.exception_message)

    @override_settings(FRONTEND_URL='https://app.example.com')
    def test_missing_code_is_logged(self):
        client = APIClient()
        res = client.get('/email-integrations/gmail/oauth/callback/?state=abc')
        self.assertEqual(res.status_code, 302)
        log = ErrorLog.objects.get()
        self.assertIn('missing code or state', log.exception_message.lower())


class GmailOAuthExchangeTests(TestCase):    @override_settings(
        GOOGLE_EMAIL_OAUTH_CLIENT_ID='id',
        GOOGLE_EMAIL_OAUTH_CLIENT_SECRET='secret',
        API_PUBLIC_BASE_URL='https://api.example.com',
    )
    @patch('emails.gmail_service._oauth_flow')
    def test_exchange_uses_flow_redirect_uri(self, mock_oauth_flow):
        flow = MagicMock()
        flow.credentials.token = 'access-token'
        flow.credentials.refresh_token = 'refresh-token'
        mock_oauth_flow.return_value = flow

        creds = _exchange_oauth_code(code='abc')

        flow.fetch_token.assert_called_once_with(code='abc')
        mock_oauth_flow.assert_called_once_with(scopes=None)
        self.assertEqual(creds.token, 'access-token')

    @override_settings(
        GOOGLE_EMAIL_OAUTH_CLIENT_ID='id',
        GOOGLE_EMAIL_OAUTH_CLIENT_SECRET='secret',
        API_PUBLIC_BASE_URL='https://api.example.com',
    )
    @patch('emails.gmail_service._oauth_flow')
    def test_exchange_accepts_scope_warning_with_token(self, mock_oauth_flow):
        flow = MagicMock()
        flow.credentials.token = 'access-token'
        flow.credentials.refresh_token = 'refresh-token'
        warning = Warning('Scope has changed')
        warning.token = {
            'access_token': 'access-token',
            'refresh_token': 'refresh-token',
            'token_type': 'Bearer',
        }
        flow.fetch_token.side_effect = warning
        mock_oauth_flow.return_value = flow

        creds = _exchange_oauth_code(code='abc')

        self.assertEqual(flow.oauth2session.token, warning.token)
        self.assertEqual(creds.token, 'access-token')

    @override_settings(
        GOOGLE_EMAIL_OAUTH_CLIENT_ID='id',
        GOOGLE_EMAIL_OAUTH_CLIENT_SECRET='secret',
        API_PUBLIC_BASE_URL='https://api.example.com',
    )
    @patch('emails.gmail_service._oauth_flow')
    def test_exchange_wraps_invalid_grant_as_gmail_oauth_error(self, mock_oauth_flow):
        flow = MagicMock()
        flow.fetch_token.side_effect = Exception('invalid_grant: Bad Request')
        mock_oauth_flow.return_value = flow

        with self.assertRaises(GmailOAuthError) as ctx:
            _exchange_oauth_code(code='abc')

        self.assertIn('API_PUBLIC_BASE_URL', str(ctx.exception))


class GmailIntegrationStatusTests(TestCase):
    def test_disconnected_payload(self):
        data = integration_status_payload(None)
        self.assertFalse(data['connected'])
        self.assertEqual(data['google_email'], '')

    @override_settings(
        GOOGLE_EMAIL_OAUTH_CLIENT_ID='id',
        GOOGLE_EMAIL_OAUTH_CLIENT_SECRET='secret',
    )
    def test_connected_payload(self):
        integration = GmailIntegration(
            google_email='user@gmail.com',
            refresh_token_encrypted='enc',
        )
        data = integration_status_payload(integration)
        self.assertTrue(data['connected'])
        self.assertEqual(data['google_email'], 'user@gmail.com')

    @override_settings(
        GOOGLE_EMAIL_OAUTH_CLIENT_ID='',
        GOOGLE_EMAIL_OAUTH_CLIENT_SECRET='',
        GOOGLE_CALENDAR_OAUTH_CLIENT_ID='calendar-id',
        GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET='calendar-secret',
    )
    def test_configured_when_calendar_oauth_credentials_present(self):
        self.assertTrue(google_oauth_configured())
        data = integration_status_payload(None)
        self.assertTrue(data['configured'])
