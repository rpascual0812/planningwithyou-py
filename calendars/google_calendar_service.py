"""Google Calendar OAuth, sync, and disconnect."""

from __future__ import annotations

import os

# Google may return a narrower scope set than requested; allow token exchange.
os.environ.setdefault('OAUTHLIB_RELAX_TOKEN_SCOPE', '1')

import contextvars
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .google_token_crypto import decrypt_token, encrypt_token
from .models import Calendar, CalendarStatus, GoogleCalendarIntegration

logger = logging.getLogger(__name__)

PWY_EVENT_ID_KEY = 'pwy_event_id'
INITIAL_SYNC_LOOKBACK_DAYS = 730
OAUTH_STATE_MAX_AGE = 600
STATE_SIGNER = TimestampSigner(salt='google-calendar-oauth')

RECONNECT_MESSAGE = (
    'Google Calendar access has expired or was revoked. '
    'Reconnect Google Calendar in Calendar Settings.'
)

skip_google_sync: contextvars.ContextVar[bool] = contextvars.ContextVar(
    'skip_google_sync',
    default=False,
)

SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
]


class GoogleCalendarConfigError(Exception):
    pass


class GoogleCalendarOAuthError(Exception):
    pass


def google_oauth_configured() -> bool:
    return bool(
        (getattr(settings, 'GOOGLE_CALENDAR_OAUTH_CLIENT_ID', '') or '').strip()
        and (getattr(settings, 'GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET', '') or '').strip()
    )


def oauth_redirect_uri() -> str:
    base = (getattr(settings, 'API_PUBLIC_BASE_URL', '') or '').rstrip('/')
    return f'{base}/calendar-integrations/google/oauth/callback/'


def webhook_url() -> str:
    base = (getattr(settings, 'API_PUBLIC_BASE_URL', '') or '').rstrip('/')
    return f'{base}/webhooks/google-calendar/'


def _require_config() -> None:
    if not google_oauth_configured():
        raise GoogleCalendarConfigError(
            'Google Calendar OAuth is not configured on the server.',
        )


def _oauth_flow(*, scopes: list[str] | None = SCOPES) -> Flow:
    _require_config()
    client_config = {
        'web': {
            'client_id': settings.GOOGLE_CALENDAR_OAUTH_CLIENT_ID,
            'client_secret': settings.GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': [oauth_redirect_uri()],
        },
    }
    return Flow.from_client_config(
        client_config,
        scopes=scopes,
        redirect_uri=oauth_redirect_uri(),
    )


def sign_oauth_state(
    *,
    account_id: int,
    company_id: int,
    user_id: int,
    sync_mode: str,
) -> str:
    payload = json.dumps(
        {
            'account_id': account_id,
            'company_id': company_id,
            'user_id': user_id,
            'sync_mode': sync_mode,
            'nonce': secrets.token_urlsafe(16),
        },
        separators=(',', ':'),
    )
    return STATE_SIGNER.sign(payload)


def unsign_oauth_state(state: str) -> dict[str, Any]:
    try:
        raw = STATE_SIGNER.unsign(state, max_age=OAUTH_STATE_MAX_AGE)
    except SignatureExpired as exc:
        raise GoogleCalendarOAuthError('OAuth session expired. Please try again.') from exc
    except BadSignature as exc:
        raise GoogleCalendarOAuthError('Invalid OAuth state.') from exc
    return json.loads(raw)


def build_authorization_url(
    *,
    account_id: int,
    company_id: int,
    user_id: int,
    sync_mode: str,
) -> str:
    flow = _oauth_flow()
    state = sign_oauth_state(
        account_id=account_id,
        company_id=company_id,
        user_id=user_id,
        sync_mode=sync_mode,
    )
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=state,
    )
    return auth_url


def get_integration_for_user(user) -> GoogleCalendarIntegration | None:
    if not user.account_id or not user.company_id:
        return None
    return GoogleCalendarIntegration.objects.filter(
        account_id=user.account_id,
        company_id=user.company_id,
    ).first()


def integration_status_payload(integration: GoogleCalendarIntegration | None) -> dict:
    configured = google_oauth_configured()
    redirect_uri = oauth_redirect_uri() if configured else None
    if integration is None or not (integration.refresh_token_encrypted or '').strip():
        return {
            'connected': False,
            'configured': configured,
            'google_email': '',
            'sync_mode': GoogleCalendarIntegration.SyncMode.ONE_WAY,
            'two_way_sync': False,
            'last_synced_at': None,
            'oauth_redirect_uri': redirect_uri,
        }
    return {
        'connected': True,
        'configured': configured,
        'google_email': integration.google_email,
        'sync_mode': integration.sync_mode,
        'two_way_sync': integration.sync_mode == GoogleCalendarIntegration.SyncMode.TWO_WAY,
        'last_synced_at': (
            integration.last_synced_at.isoformat() if integration.last_synced_at else None
        ),
        'oauth_redirect_uri': redirect_uri,
    }


def _expiry_for_db(dt: datetime | None) -> datetime | None:
    """Persist OAuth expiry in Django (USE_TZ expects aware UTC)."""
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc)


def _expiry_for_google_auth(dt: datetime | None) -> datetime | None:
    """google-auth compares expiry to naive datetime.utcnow()."""
    if dt is None:
        return None
    if timezone.is_aware(dt):
        return dt.astimezone(dt_timezone.utc).replace(tzinfo=None)
    return dt


def _store_credentials_on_integration(
    integration: GoogleCalendarIntegration,
    credentials: Credentials,
    *,
    google_email: str = '',
) -> GoogleCalendarIntegration:
    integration.access_token_encrypted = encrypt_token(credentials.token or '')
    if credentials.refresh_token:
        integration.refresh_token_encrypted = encrypt_token(credentials.refresh_token)
    integration.token_expiry = _expiry_for_db(credentials.expiry)
    if google_email:
        integration.google_email = google_email
    if integration.created_at is None:
        integration.created_at = timezone.now()
    integration.save()
    return integration


def _invalidate_integration_oauth(integration: GoogleCalendarIntegration) -> None:
    """Drop stored tokens after refresh failure so the app shows disconnected."""
    integration.access_token_encrypted = ''
    integration.refresh_token_encrypted = ''
    integration.token_expiry = None
    integration.watch_channel_id = ''
    integration.watch_resource_id = ''
    integration.watch_channel_token = ''
    integration.watch_expiration = None
    integration.google_sync_token = ''
    integration.save(
        update_fields=[
            'access_token_encrypted',
            'refresh_token_encrypted',
            'token_expiry',
            'watch_channel_id',
            'watch_resource_id',
            'watch_channel_token',
            'watch_expiration',
            'google_sync_token',
            'updated_at',
        ],
    )


def _credentials_from_integration(
    integration: GoogleCalendarIntegration,
) -> Credentials | None:
    refresh = decrypt_token(integration.refresh_token_encrypted)
    if not refresh:
        return None
    access = decrypt_token(integration.access_token_encrypted)
    creds = Credentials(
        token=access or None,
        refresh_token=refresh,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_CALENDAR_OAUTH_CLIENT_ID,
        client_secret=settings.GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.expiry = _expiry_for_google_auth(integration.token_expiry)
    if not creds.valid and creds.refresh_token:
        from google.auth.transport.requests import Request

        try:
            creds.refresh(Request())
        except RefreshError as exc:
            logger.warning(
                'Google Calendar OAuth refresh failed integration_id=%s company_id=%s: %s',
                integration.pk,
                integration.company_id,
                exc,
            )
            _invalidate_integration_oauth(integration)
            try:
                from user_notifications.services import notify_google_calendar_token_revoked

                notify_google_calendar_token_revoked(
                    user_id=integration.created_by_id,
                    account_id=integration.account_id,
                    company_id=integration.company_id,
                    integration_id=integration.pk,
                    error_message=str(exc),
                )
            except Exception:
                logger.exception('Failed to create Google Calendar user notification')
            return None
        _store_credentials_on_integration(integration, creds)
    return creds


def _calendar_service(integration: GoogleCalendarIntegration):
    creds = _credentials_from_integration(integration)
    if creds is None:
        raise GoogleCalendarOAuthError(RECONNECT_MESSAGE)
    return build('calendar', 'v3', credentials=creds, cache_discovery=False)


def _fetch_google_email(credentials: Credentials) -> str:
    try:
        resp = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {credentials.token}'},
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            return str(data.get('email') or '')
    except requests.RequestException:
        logger.exception('Failed to fetch Google user email')
    return ''


def _credentials_from_oauth_flow(flow: Flow) -> Credentials:
    credentials = flow.credentials
    if credentials is not None and credentials.token:
        return credentials

    token = flow.oauth2session.token or {}
    access_token = token.get('access_token') if isinstance(token, dict) else None
    if not access_token:
        raise GoogleCalendarOAuthError('Google did not return OAuth credentials.')

    scope_value = token.get('scope') if isinstance(token, dict) else None
    scopes = scope_value.split() if isinstance(scope_value, str) and scope_value else None
    return Credentials(
        token=access_token,
        refresh_token=token.get('refresh_token') if isinstance(token, dict) else None,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_CALENDAR_OAUTH_CLIENT_ID,
        client_secret=settings.GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET,
        scopes=scopes,
    )


def _exchange_oauth_code(*, code: str) -> Credentials:
    flow = _oauth_flow(scopes=None)
    try:
        flow.fetch_token(code=code)
    except Warning as exc:
        token = getattr(exc, 'token', None)
        if token:
            flow.oauth2session.token = token
        else:
            raise GoogleCalendarOAuthError(
                'Google returned unexpected OAuth scopes. Please try again.',
            ) from exc
    except Exception as exc:
        if isinstance(exc, GoogleCalendarOAuthError):
            raise
        logger.exception('Google Calendar OAuth token exchange failed')
        message = str(exc).strip() or exc.__class__.__name__
        if 'invalid_grant' in message.lower():
            message = (
                'Google rejected the authorization code. '
                'Confirm API_PUBLIC_BASE_URL matches the Google Calendar redirect URI, '
                'then try connecting again.'
            )
        raise GoogleCalendarOAuthError(message) from exc

    return _credentials_from_oauth_flow(flow)


def complete_oauth_callback(*, code: str, state: str) -> GoogleCalendarIntegration:
    payload = unsign_oauth_state(state)
    credentials = _exchange_oauth_code(code=code)
    google_email = _fetch_google_email(credentials)
    account_id = int(payload['account_id'])
    company_id = int(payload['company_id'])
    user_id = int(payload['user_id'])
    sync_mode = payload.get('sync_mode') or GoogleCalendarIntegration.SyncMode.ONE_WAY
    if sync_mode not in GoogleCalendarIntegration.SyncMode.values:
        sync_mode = GoogleCalendarIntegration.SyncMode.ONE_WAY

    integration, _created = GoogleCalendarIntegration.objects.update_or_create(
        account_id=account_id,
        company_id=company_id,
        defaults={
            'google_calendar_id': 'primary',
            'sync_mode': sync_mode,
            'google_sync_token': '',
            'created_by_id': user_id,
        },
    )
    if not credentials.refresh_token and not (
        integration.refresh_token_encrypted or ''
    ).strip():
        raise GoogleCalendarOAuthError(
            'Google did not return a refresh token. Please try connecting again.',
        )
    _store_credentials_on_integration(
        integration,
        credentials,
        google_email=google_email,
    )
    integration.refresh_from_db()
    backfill_events_to_google(integration)
    if integration.sync_mode == GoogleCalendarIntegration.SyncMode.TWO_WAY:
        register_watch_channel(integration)
        sync_events_from_google(integration)
    integration.last_synced_at = timezone.now()
    integration.save(update_fields=['last_synced_at', 'updated_at'])
    return integration


def frontend_redirect_url(*, success: bool, message: str = '') -> str:
    base = (getattr(settings, 'FRONTEND_URL', '') or '').rstrip('/')
    params = {'tab': 'calendar', 'google_calendar': 'connected' if success else 'error'}
    if message:
        params['google_calendar_message'] = message
    return f'{base}/settings?{urlencode(params)}'


def _to_utc_aware(dt: datetime) -> datetime:
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc)


def _format_google_datetime(dt: datetime) -> str:
    """RFC3339 UTC instant for Google Calendar API."""
    return _to_utc_aware(dt).strftime('%Y-%m-%dT%H:%M:%SZ')


def _event_body(calendar_event: Calendar) -> dict:
    return {
        'summary': calendar_event.title,
        'location': calendar_event.location or '',
        'start': {'dateTime': _format_google_datetime(calendar_event.start)},
        'end': {'dateTime': _format_google_datetime(calendar_event.end)},
        'extendedProperties': {
            'private': {PWY_EVENT_ID_KEY: str(calendar_event.id)},
        },
    }


def _log_google_http_error(action: str, calendar_event: Calendar, exc: HttpError) -> None:
    detail = ''
    try:
        detail = exc.content.decode('utf-8') if exc.content else str(exc)
    except Exception:
        detail = str(exc)
    logger.error(
        'Google Calendar %s failed event_id=%s status=%s body=%s',
        action,
        calendar_event.pk,
        exc.resp.status if exc.resp else '?',
        detail,
    )


def push_event_to_google(calendar_event: Calendar | int) -> None:
    if skip_google_sync.get():
        return
    if isinstance(calendar_event, int):
        calendar_event = (
            Calendar.objects.filter(pk=calendar_event, deleted_at__isnull=True).first()
        )
        if calendar_event is None:
            return
    integration = GoogleCalendarIntegration.objects.filter(
        account_id=calendar_event.account_id,
        company_id=calendar_event.company_id,
    ).first()
    if integration is None:
        return
    if not (integration.refresh_token_encrypted or '').strip():
        return
    try:
        service = _calendar_service(integration)
        cal_id = integration.google_calendar_id or 'primary'
        body = _event_body(calendar_event)
        google_id = (calendar_event.google_event_id or '').strip()
        if google_id:
            try:
                service.events().update(
                    calendarId=cal_id,
                    eventId=google_id,
                    body=body,
                ).execute()
            except HttpError as exc:
                if exc.resp is not None and exc.resp.status == 404:
                    google_id = ''
                else:
                    raise
        if not google_id:
            created = (
                service.events()
                .insert(calendarId=cal_id, body=body)
                .execute()
            )
            new_id = str(created.get('id') or '')
            if new_id:
                Calendar.all_objects.filter(pk=calendar_event.pk).update(
                    google_event_id=new_id,
                )
                calendar_event.google_event_id = new_id
        integration.last_synced_at = timezone.now()
        integration.save(update_fields=['last_synced_at', 'updated_at'])
    except GoogleCalendarOAuthError as exc:
        logger.warning(
            'Google Calendar push skipped event_id=%s: %s',
            calendar_event.pk,
            exc,
        )
    except HttpError as exc:
        _log_google_http_error('push', calendar_event, exc)
    except Exception:
        logger.exception(
            'Google Calendar push failed event_id=%s',
            calendar_event.pk,
        )


def delete_event_from_google(calendar_event: Calendar) -> None:
    if skip_google_sync.get():
        return
    integration = GoogleCalendarIntegration.objects.filter(
        account_id=calendar_event.account_id,
        company_id=calendar_event.company_id,
    ).first()
    if integration is None:
        return
    google_id = (calendar_event.google_event_id or '').strip()
    if not google_id:
        return
    try:
        service = _calendar_service(integration)
        cal_id = integration.google_calendar_id or 'primary'
        service.events().delete(calendarId=cal_id, eventId=google_id).execute()
    except GoogleCalendarOAuthError as exc:
        logger.warning(
            'Google Calendar delete skipped event_id=%s: %s',
            calendar_event.pk,
            exc,
        )
    except HttpError as exc:
        if exc.resp is None or exc.resp.status != 404:
            _log_google_http_error('delete', calendar_event, exc)
    except Exception:
        logger.exception(
            'Google Calendar delete failed event_id=%s',
            calendar_event.pk,
        )


def _default_status(account_id: int) -> CalendarStatus | None:
    return (
        CalendarStatus.objects.filter(account_id=account_id)
        .order_by('sort_order', 'id')
        .first()
    )


def _parse_google_datetime(value: dict | None) -> datetime | None:
    if not value:
        return None
    raw = value.get('dateTime') or value.get('date')
    if not raw:
        return None
    if 'T' in raw:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, dt_timezone.utc)
        return parsed
    parsed = datetime.fromisoformat(raw)
    return timezone.make_aware(
        datetime.combine(parsed.date(), datetime.min.time()),
        dt_timezone.utc,
    )


def _upsert_event_from_google(
    integration: GoogleCalendarIntegration,
    item: dict,
) -> None:
    status = (item.get('status') or '').lower()
    if status == 'cancelled':
        private = (item.get('extendedProperties') or {}).get('private') or {}
        pwy_id = private.get(PWY_EVENT_ID_KEY)
        google_id = str(item.get('id') or '')
        if pwy_id:
            Calendar.all_objects.filter(
                pk=int(pwy_id),
                account_id=integration.account_id,
                company_id=integration.company_id,
            ).update(deleted_at=timezone.now())
        elif google_id:
            Calendar.all_objects.filter(
                google_event_id=google_id,
                account_id=integration.account_id,
                company_id=integration.company_id,
                deleted_at__isnull=True,
            ).update(deleted_at=timezone.now())
        return

    start = _parse_google_datetime(item.get('start'))
    end = _parse_google_datetime(item.get('end'))
    if not start or not end:
        return

    private = (item.get('extendedProperties') or {}).get('private') or {}
    pwy_id = private.get(PWY_EVENT_ID_KEY)
    google_id = str(item.get('id') or '')
    title = str(item.get('summary') or 'Untitled')
    location = str(item.get('location') or '')

    token = skip_google_sync.set(True)
    try:
        if pwy_id:
            event = Calendar.all_objects.filter(
                pk=int(pwy_id),
                account_id=integration.account_id,
                company_id=integration.company_id,
            ).first()
            if event is None:
                return
            event.title = title
            event.location = location
            event.start = start
            event.end = end
            event.google_event_id = google_id
            event.deleted_at = None
            event.save(
                update_fields=[
                    'title',
                    'location',
                    'start',
                    'end',
                    'google_event_id',
                    'deleted_at',
                ],
            )
            return

        existing = Calendar.objects.filter(
            google_event_id=google_id,
            account_id=integration.account_id,
            company_id=integration.company_id,
        ).first()
        if existing:
            existing.title = title
            existing.location = location
            existing.start = start
            existing.end = end
            existing.save(update_fields=['title', 'location', 'start', 'end'])
            return

        default_status = _default_status(integration.account_id)
        if default_status is None:
            return
        Calendar.objects.create(
            account_id=integration.account_id,
            company_id=integration.company_id,
            status=default_status,
            title=title,
            location=location,
            start=start,
            end=end,
            google_event_id=google_id,
            created_by_id=integration.created_by_id,
        )
    finally:
        skip_google_sync.reset(token)


def sync_events_from_google(integration: GoogleCalendarIntegration) -> None:
    if integration.sync_mode != GoogleCalendarIntegration.SyncMode.TWO_WAY:
        return
    try:
        service = _calendar_service(integration)
        cal_id = integration.google_calendar_id or 'primary'
        sync_token = (integration.google_sync_token or '').strip()
        page_token = None

        while True:
            params: dict[str, Any] = {
                'calendarId': cal_id,
                'singleEvents': True,
                'showDeleted': True,
                'maxResults': 250,
            }
            if page_token:
                params['pageToken'] = page_token
            elif sync_token:
                params['syncToken'] = sync_token
            else:
                params['timeMin'] = _format_google_datetime(
                    timezone.now() - timedelta(days=INITIAL_SYNC_LOOKBACK_DAYS),
                )

            result = service.events().list(**params).execute()
            for item in result.get('items', []):
                _upsert_event_from_google(integration, item)

            page_token = result.get('nextPageToken')
            if page_token:
                continue

            new_token = result.get('nextSyncToken')
            if new_token:
                integration.google_sync_token = new_token
                integration.save(update_fields=['google_sync_token', 'updated_at'])
            break

        integration.last_synced_at = timezone.now()
        integration.save(update_fields=['last_synced_at', 'updated_at'])
    except GoogleCalendarOAuthError as exc:
        logger.warning(
            'Google Calendar inbound sync skipped integration_id=%s: %s',
            integration.pk,
            exc,
        )
    except HttpError as exc:
        if exc.resp is not None and exc.resp.status == 410:
            integration.google_sync_token = ''
            integration.save(update_fields=['google_sync_token', 'updated_at'])
            sync_events_from_google(integration)
            return
        logger.exception('Google Calendar inbound sync failed')
    except Exception:
        logger.exception('Google Calendar inbound sync failed')


def backfill_events_to_google(integration: GoogleCalendarIntegration) -> None:
    """Push all existing app appointments to Google (including pre-connection events)."""
    event_ids = list(
        Calendar.objects.filter(
            account_id=integration.account_id,
            company_id=integration.company_id,
        ).values_list('pk', flat=True),
    )
    for event_id in event_ids:
        push_event_to_google(event_id)
    integration.last_synced_at = timezone.now()
    integration.save(update_fields=['last_synced_at', 'updated_at'])


def run_full_google_sync(integration: GoogleCalendarIntegration) -> None:
    """Outbound backfill plus inbound sync when two-way is enabled."""
    backfill_events_to_google(integration)
    if integration.sync_mode == GoogleCalendarIntegration.SyncMode.TWO_WAY:
        sync_events_from_google(integration)


def schedule_inbound_sync(integration_id: int) -> None:
    integration = GoogleCalendarIntegration.objects.filter(pk=integration_id).first()
    if integration is None:
        return
    sync_events_from_google(integration)


def register_watch_channel(integration: GoogleCalendarIntegration) -> None:
    if integration.sync_mode != GoogleCalendarIntegration.SyncMode.TWO_WAY:
        return
    stop_watch_channel(integration, save=False)
    channel_id = str(uuid.uuid4())
    channel_token = secrets.token_urlsafe(24)
    try:
        service = _calendar_service(integration)
        cal_id = integration.google_calendar_id or 'primary'
        body = {
            'id': channel_id,
            'type': 'web_hook',
            'address': webhook_url(),
            'token': channel_token,
        }
        resp = service.events().watch(calendarId=cal_id, body=body).execute()
        expiration_ms = resp.get('expiration')
        expiration = None
        if expiration_ms:
            expiration = datetime.fromtimestamp(
                int(expiration_ms) / 1000,
                tz=dt_timezone.utc,
            )
        integration.watch_channel_id = channel_id
        integration.watch_resource_id = str(resp.get('resourceId') or '')
        integration.watch_channel_token = channel_token
        integration.watch_expiration = expiration
        integration.save(
            update_fields=[
                'watch_channel_id',
                'watch_resource_id',
                'watch_channel_token',
                'watch_expiration',
                'updated_at',
            ],
        )
    except GoogleCalendarOAuthError as exc:
        logger.warning(
            'Google Calendar watch registration skipped integration_id=%s: %s',
            integration.pk,
            exc,
        )
    except Exception:
        logger.exception('Failed to register Google Calendar watch channel')


def stop_watch_channel(
    integration: GoogleCalendarIntegration,
    *,
    save: bool = True,
) -> None:
    channel_id = (integration.watch_channel_id or '').strip()
    resource_id = (integration.watch_resource_id or '').strip()
    if channel_id and resource_id:
        try:
            service = _calendar_service(integration)
            service.channels().stop(
                body={'id': channel_id, 'resourceId': resource_id},
            ).execute()
        except Exception:
            logger.exception('Failed to stop Google Calendar watch channel')
    integration.watch_channel_id = ''
    integration.watch_resource_id = ''
    integration.watch_channel_token = ''
    integration.watch_expiration = None
    if save:
        integration.save(
            update_fields=[
                'watch_channel_id',
                'watch_resource_id',
                'watch_channel_token',
                'watch_expiration',
                'updated_at',
            ],
        )


def revoke_google_tokens(integration: GoogleCalendarIntegration) -> None:
    refresh = ''
    try:
        refresh = decrypt_token(integration.refresh_token_encrypted)
    except ValueError:
        pass
    if refresh:
        try:
            requests.post(
                'https://oauth2.googleapis.com/revoke',
                params={'token': refresh},
                timeout=15,
            )
        except requests.RequestException:
            logger.exception('Failed to revoke Google refresh token')


def disconnect_integration(integration: GoogleCalendarIntegration) -> None:
    stop_watch_channel(integration, save=False)
    revoke_google_tokens(integration)
    Calendar.all_objects.filter(
        account_id=integration.account_id,
        company_id=integration.company_id,
    ).update(google_event_id='')
    integration.delete()


def update_sync_mode(
    integration: GoogleCalendarIntegration,
    *,
    two_way_sync: bool,
) -> GoogleCalendarIntegration:
    new_mode = (
        GoogleCalendarIntegration.SyncMode.TWO_WAY
        if two_way_sync
        else GoogleCalendarIntegration.SyncMode.ONE_WAY
    )
    integration.sync_mode = new_mode
    integration.save(update_fields=['sync_mode', 'updated_at'])
    if new_mode == GoogleCalendarIntegration.SyncMode.TWO_WAY:
        integration.google_sync_token = ''
        integration.save(update_fields=['google_sync_token', 'updated_at'])
        register_watch_channel(integration)
        sync_events_from_google(integration)
    else:
        stop_watch_channel(integration)
        integration.google_sync_token = ''
        integration.save(update_fields=['google_sync_token', 'updated_at'])
    return integration


def find_integration_for_webhook(
    channel_id: str,
    channel_token: str,
) -> GoogleCalendarIntegration | None:
    if not channel_id or not channel_token:
        return None
    return GoogleCalendarIntegration.objects.filter(
        watch_channel_id=channel_id,
        watch_channel_token=channel_token,
    ).first()
