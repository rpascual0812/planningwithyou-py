from django.test import TestCase, override_settings

from emails.gmail_service import google_oauth_configured, integration_status_payload
from emails.models import GmailIntegration


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
