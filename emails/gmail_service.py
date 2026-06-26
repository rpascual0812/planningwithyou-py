"""Gmail OAuth and outbound send via Gmail API."""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
from datetime import datetime, timezone as dt_timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from urllib.parse import urlencode

# Google may return a broader scope set than requested (incremental auth).
os.environ.setdefault('OAUTHLIB_RELAX_TOKEN_SCOPE', '1')

import requests
from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from calendars.google_token_crypto import decrypt_token, encrypt_token

from .attachment_refs import resolve_attachment_item
from .mail import _prepare_message_parts
from .models import EmailLog, GmailIntegration

logger = logging.getLogger(__name__)

OAUTH_STATE_MAX_AGE = 600
STATE_SIGNER = TimestampSigner(salt='gmail-oauth')

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
]


class GmailConfigError(Exception):
    pass


class GmailOAuthError(Exception):
    pass


def _resolved_oauth_client_id() -> str:
    email_id = (getattr(settings, 'GOOGLE_EMAIL_OAUTH_CLIENT_ID', '') or '').strip()
    if email_id:
        return email_id
    return (getattr(settings, 'GOOGLE_CALENDAR_OAUTH_CLIENT_ID', '') or '').strip()


def _resolved_oauth_client_secret() -> str:
    email_secret = (
        getattr(settings, 'GOOGLE_EMAIL_OAUTH_CLIENT_SECRET', '') or ''
    ).strip()
    if email_secret:
        return email_secret
    return (getattr(settings, 'GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET', '') or '').strip()


def google_oauth_configured() -> bool:
    return bool(_resolved_oauth_client_id() and _resolved_oauth_client_secret())


def oauth_redirect_uri() -> str:
    base = (getattr(settings, 'API_PUBLIC_BASE_URL', '') or '').rstrip('/')
    return f'{base}/email-integrations/gmail/oauth/callback/'


def _require_config() -> None:
    if not google_oauth_configured():
        raise GmailConfigError(
            'Gmail OAuth is not configured on the server '
            '(set GOOGLE_EMAIL_OAUTH_CLIENT_ID/SECRET or reuse '
            'GOOGLE_CALENDAR_OAUTH_CLIENT_ID/SECRET).',
        )


def _oauth_flow(*, scopes: list[str] | None = SCOPES) -> Flow:
    _require_config()
    client_config = {
        'web': {
            'client_id': _resolved_oauth_client_id(),
            'client_secret': _resolved_oauth_client_secret(),
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


def _expiry_for_db(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    from django.utils import timezone

    if timezone.is_naive(dt):
        return timezone.make_aware(dt, dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc)


def _expiry_for_google_auth(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    from django.utils import timezone

    if timezone.is_aware(dt):
        return dt.astimezone(dt_timezone.utc).replace(tzinfo=None)
    return dt


def sign_oauth_state(
    *,
    account_id: int,
    company_id: int,
    user_id: int,
) -> str:
    payload = json.dumps(
        {
            'account_id': account_id,
            'company_id': company_id,
            'user_id': user_id,
            'nonce': secrets.token_urlsafe(16),
        },
        separators=(',', ':'),
    )
    return STATE_SIGNER.sign(payload)


def unsign_oauth_state(state: str) -> dict[str, Any]:
    try:
        raw = STATE_SIGNER.unsign(state, max_age=OAUTH_STATE_MAX_AGE)
    except SignatureExpired as exc:
        raise GmailOAuthError('OAuth session expired. Please try again.') from exc
    except BadSignature as exc:
        raise GmailOAuthError('Invalid OAuth state.') from exc
    return json.loads(raw)


def build_authorization_url(
    *,
    account_id: int,
    company_id: int,
    user_id: int,
) -> str:
    flow = _oauth_flow()
    state = sign_oauth_state(
        account_id=account_id,
        company_id=company_id,
        user_id=user_id,
    )
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=state,
    )
    return auth_url


def get_gmail_integration(
    account_id: int | None,
    company_id: int | None,
) -> GmailIntegration | None:
    if not account_id or not company_id:
        return None
    return GmailIntegration.objects.filter(
        account_id=account_id,
        company_id=company_id,
    ).first()


def get_integration_for_user(user) -> GmailIntegration | None:
    if not user.account_id or not user.company_id:
        return None
    return get_gmail_integration(user.account_id, user.company_id)


def integration_status_payload(integration: GmailIntegration | None) -> dict:
    configured = google_oauth_configured()
    redirect_uri = oauth_redirect_uri() if configured else None
    if integration is None or not (integration.refresh_token_encrypted or '').strip():
        return {
            'connected': False,
            'configured': configured,
            'google_email': '',
            'oauth_redirect_uri': redirect_uri,
        }
    return {
        'connected': True,
        'configured': configured,
        'google_email': integration.google_email,
        'oauth_redirect_uri': redirect_uri,
    }


def is_gmail_connected(account_id: int | None, company_id: int | None) -> bool:
    integration = get_gmail_integration(account_id, company_id)
    return bool(
        integration and (integration.refresh_token_encrypted or '').strip(),
    )


def resolve_sender_email(
    account_id: int | None,
    company_id: int | None,
) -> str:
    integration = get_gmail_integration(account_id, company_id)
    if integration and (integration.google_email or '').strip():
        return integration.google_email.strip()
    return (getattr(settings, 'MAILJET_SEND_FROM', '') or '').strip()


def _store_credentials_on_integration(
    integration: GmailIntegration,
    credentials: Credentials,
    *,
    google_email: str = '',
) -> GmailIntegration:
    from django.utils import timezone

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


def _invalidate_gmail_integration(integration: GmailIntegration) -> None:
    integration.access_token_encrypted = ''
    integration.refresh_token_encrypted = ''
    integration.token_expiry = None
    integration.save(
        update_fields=[
            'access_token_encrypted',
            'refresh_token_encrypted',
            'token_expiry',
            'updated_at',
        ],
    )


def _credentials_from_integration(
    integration: GmailIntegration,
) -> Credentials | None:
    refresh = decrypt_token(integration.refresh_token_encrypted)
    if not refresh:
        return None
    access = decrypt_token(integration.access_token_encrypted)
    creds = Credentials(
        token=access or None,
        refresh_token=refresh,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=_resolved_oauth_client_id(),
        client_secret=_resolved_oauth_client_secret(),
        scopes=SCOPES,
    )
    creds.expiry = _expiry_for_google_auth(integration.token_expiry)
    if not creds.valid and creds.refresh_token:
        from google.auth.transport.requests import Request

        try:
            creds.refresh(Request())
        except RefreshError as exc:
            logger.warning(
                'Gmail OAuth refresh failed integration_id=%s company_id=%s: %s',
                integration.pk,
                integration.company_id,
                exc,
            )
            _invalidate_gmail_integration(integration)
            try:
                from user_notifications.services import notify_gmail_token_revoked

                notify_gmail_token_revoked(
                    user_id=integration.created_by_id,
                    account_id=integration.account_id,
                    company_id=integration.company_id,
                    integration_id=integration.pk,
                    error_message=str(exc),
                )
            except Exception:
                logger.exception('Failed to create Gmail user notification')
            return None
        _store_credentials_on_integration(integration, creds)
    return creds


def _gmail_service(integration: GmailIntegration):
    creds = _credentials_from_integration(integration)
    if creds is None:
        raise GmailOAuthError('Gmail is not connected.')
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


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
        raise GmailOAuthError('Google did not return OAuth credentials.')

    scope_value = token.get('scope') if isinstance(token, dict) else None
    scopes = scope_value.split() if isinstance(scope_value, str) and scope_value else None
    return Credentials(
        token=access_token,
        refresh_token=token.get('refresh_token') if isinstance(token, dict) else None,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=_resolved_oauth_client_id(),
        client_secret=_resolved_oauth_client_secret(),
        scopes=scopes,
    )


def _exchange_oauth_code(*, code: str) -> Credentials:
    # Do not pin scopes during token exchange; Google may return combined scopes
    # when include_granted_scopes is used (e.g. after Calendar was connected).
    flow = _oauth_flow(scopes=None)
    try:
        flow.fetch_token(code=code)
    except Warning as exc:
        token = getattr(exc, 'token', None)
        if token:
            flow.oauth2session.token = token
        else:
            raise GmailOAuthError(
                'Google returned unexpected OAuth scopes. Please try again.',
            ) from exc
    except Exception as exc:
        if isinstance(exc, GmailOAuthError):
            raise
        logger.exception('Gmail OAuth token exchange failed')
        message = str(exc).strip() or exc.__class__.__name__
        if 'invalid_grant' in message.lower():
            message = (
                'Google rejected the authorization code. '
                'Confirm API_PUBLIC_BASE_URL matches the Gmail redirect URI, '
                'then try connecting again.'
            )
        raise GmailOAuthError(message) from exc

    return _credentials_from_oauth_flow(flow)


def complete_oauth_callback(*, code: str, state: str) -> GmailIntegration:
    payload = unsign_oauth_state(state)
    credentials = _exchange_oauth_code(code=code)
    google_email = _fetch_google_email(credentials)
    account_id = int(payload['account_id'])
    company_id = int(payload['company_id'])
    user_id = int(payload['user_id'])

    integration, _created = GmailIntegration.objects.update_or_create(
        account_id=account_id,
        company_id=company_id,
        defaults={'created_by_id': user_id},
    )
    if not credentials.refresh_token and not (
        integration.refresh_token_encrypted or ''
    ).strip():
        raise GmailOAuthError(
            'Google did not return a refresh token. Please try connecting again.',
        )
    _store_credentials_on_integration(
        integration,
        credentials,
        google_email=google_email,
    )
    return integration


def frontend_redirect_url(*, success: bool, message: str = '') -> str:
    base = (getattr(settings, 'FRONTEND_URL', '') or '').rstrip('/')
    params = {'tab': 'email-settings', 'gmail': 'connected' if success else 'error'}
    if message:
        params['gmail_message'] = message
    return f'{base}/settings?{urlencode(params)}'


def revoke_google_tokens(integration: GmailIntegration) -> None:
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


def disconnect_integration(integration: GmailIntegration) -> None:
    revoke_google_tokens(integration)
    integration.delete()


def _format_from_header(integration: GmailIntegration) -> str:
    email = (integration.google_email or '').strip()
    name = (getattr(settings, 'MAILJET_SENDER_NAME', '') or '').strip()
    if name and email:
        return f'{name} <{email}>'
    return email


def _build_gmail_raw_message(log: EmailLog, integration: GmailIntegration) -> str:
    html_part, text_part = _prepare_message_parts(log.body)
    root = MIMEMultipart('mixed')
    root['Subject'] = log.subject
    root['From'] = _format_from_header(integration)
    root['To'] = ', '.join(log.to)
    if log.cc:
        root['Cc'] = ', '.join(log.cc)
    if log.reply_to:
        root['Reply-To'] = log.reply_to

    body_root = MIMEMultipart('alternative')
    body_root.attach(MIMEText(text_part, 'plain', 'utf-8'))
    body_root.attach(MIMEText(html_part, 'html', 'utf-8'))
    root.attach(body_root)

    attachment_items = [item for item in (log.attachments or []) if item not in (None, '')]
    for item in attachment_items:
        raw, filename, content_type = resolve_attachment_item(
            item,
            account_id=log.account_id,
            company_id=log.company_id,
        )
        part = MIMEBase(*content_type.split('/', 1) if '/' in content_type else ('application', 'octet-stream'))
        part.set_payload(raw)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment', filename=filename)
        root.attach(part)

    return base64.urlsafe_b64encode(root.as_bytes()).decode('ascii')


def send_email_via_gmail(log: EmailLog, integration: GmailIntegration) -> None:
    service = _gmail_service(integration)
    raw = _build_gmail_raw_message(log, integration)
    body: dict[str, Any] = {'raw': raw}
    if log.bcc:
        body['bcc'] = ', '.join(log.bcc)
    try:
        service.users().messages().send(userId='me', body=body).execute()
    except HttpError as exc:
        detail = ''
        try:
            detail = exc.content.decode('utf-8') if exc.content else str(exc)
        except Exception:
            detail = str(exc)
        raise RuntimeError(f'Gmail API error: {detail}') from exc
