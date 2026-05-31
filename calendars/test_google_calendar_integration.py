from django.test import TestCase, override_settings
from django.utils import timezone

from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone

from google.oauth2.credentials import Credentials

from calendars.google_calendar_service import (
    _expiry_for_google_auth,
    _format_google_datetime,
    integration_status_payload,
    sign_oauth_state,
    unsign_oauth_state,
)
from calendars.models import GoogleCalendarIntegration


class GoogleCalendarCredentialExpiryTests(TestCase):
    def test_aware_expiry_does_not_break_google_auth_expired_check(self):
        aware_expiry = timezone.now() + timedelta(hours=1)
        naive_expiry = _expiry_for_google_auth(aware_expiry)
        self.assertIsNotNone(naive_expiry)
        self.assertIsNone(naive_expiry.tzinfo)
        creds = Credentials(token='access-token', expiry=naive_expiry)
        self.assertFalse(creds.expired)


class GoogleCalendarDatetimeFormatTests(TestCase):
    def test_format_google_datetime_utc_z_suffix(self):
        dt = datetime(2024, 6, 15, 14, 30, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(_format_google_datetime(dt), '2024-06-15T14:30:00Z')


class GoogleCalendarOAuthStateTests(TestCase):
    def test_sign_and_unsign_state(self):
        state = sign_oauth_state(
            account_id=1,
            company_id=2,
            user_id=3,
            sync_mode='two_way',
        )
        payload = unsign_oauth_state(state)
        self.assertEqual(payload['account_id'], 1)
        self.assertEqual(payload['company_id'], 2)
        self.assertEqual(payload['user_id'], 3)
        self.assertEqual(payload['sync_mode'], 'two_way')


class GoogleCalendarStatusPayloadTests(TestCase):
    def test_disconnected_payload(self):
        data = integration_status_payload(None)
        self.assertFalse(data['connected'])
        self.assertFalse(data['two_way_sync'])

    @override_settings(
        GOOGLE_CALENDAR_OAUTH_CLIENT_ID='id',
        GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET='secret',
    )
    def test_connected_payload(self):
        integration = GoogleCalendarIntegration(
            google_email='user@example.com',
            sync_mode=GoogleCalendarIntegration.SyncMode.TWO_WAY,
            refresh_token_encrypted='enc',
            last_synced_at=timezone.now(),
        )
        data = integration_status_payload(integration)
        self.assertTrue(data['connected'])
        self.assertTrue(data['two_way_sync'])
        self.assertEqual(data['google_email'], 'user@example.com')
