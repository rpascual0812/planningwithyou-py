from __future__ import annotations

from django.utils import timezone

from .models import UserNotification

FRONTEND_CALENDAR_SETTINGS_URL = '/settings?tab=calendar&section=integrations'
FRONTEND_EMAIL_SETTINGS_URL = '/settings?tab=email-settings'


def notify_user(
    *,
    user_id: int,
    account_id: int,
    title: str,
    message: str,
    category: str = UserNotification.Category.GENERAL,
    severity: str = UserNotification.Severity.ERROR,
    company_id: int | None = None,
    action_url: str = '',
    dedupe_key: str = '',
) -> UserNotification | None:
    """Create or refresh an unread notification for a user."""
    if not user_id:
        return None

    if dedupe_key:
        existing = (
            UserNotification.objects.filter(
                user_id=user_id,
                dedupe_key=dedupe_key,
                read_at__isnull=True,
            )
            .order_by('-created_at', '-id')
            .first()
        )
        if existing is not None:
            existing.title = title
            existing.message = message
            existing.severity = severity
            existing.action_url = action_url or existing.action_url
            existing.updated_at = timezone.now()
            existing.save(
                update_fields=[
                    'title',
                    'message',
                    'severity',
                    'action_url',
                    'updated_at',
                ],
            )
            return existing

    return UserNotification.objects.create(
        user_id=user_id,
        account_id=account_id,
        company_id=company_id,
        category=category,
        severity=severity,
        title=title,
        message=message,
        action_url=action_url,
        dedupe_key=dedupe_key,
    )


def notify_google_calendar_token_revoked(
    *,
    user_id: int,
    account_id: int,
    company_id: int | None,
    integration_id: int,
    error_message: str,
) -> UserNotification | None:
    detail = (error_message or '').strip()
    if 'invalid_grant' in detail.lower():
        detail = 'Your Google Calendar connection expired or was revoked.'
    return notify_user(
        user_id=user_id,
        account_id=account_id,
        company_id=company_id,
        category=UserNotification.Category.GOOGLE_CALENDAR,
        severity=UserNotification.Severity.ERROR,
        title='Google Calendar disconnected',
        message=(
            f'{detail} Reconnect Google Calendar in Calendar Settings '
            'to resume syncing appointments.'
        ),
        action_url=FRONTEND_CALENDAR_SETTINGS_URL,
        dedupe_key=f'google_calendar:integration:{integration_id}',
    )


def notify_gmail_token_revoked(
    *,
    user_id: int,
    account_id: int,
    company_id: int | None,
    integration_id: int,
    error_message: str,
) -> UserNotification | None:
    detail = (error_message or '').strip()
    if 'invalid_grant' in detail.lower():
        detail = 'Your Gmail connection expired or was revoked.'
    return notify_user(
        user_id=user_id,
        account_id=account_id,
        company_id=company_id,
        category=UserNotification.Category.GMAIL,
        severity=UserNotification.Severity.ERROR,
        title='Gmail disconnected',
        message=(
            f'{detail} Reconnect Gmail in Email Settings to resume sending email.'
        ),
        action_url=FRONTEND_EMAIL_SETTINGS_URL,
        dedupe_key=f'gmail:integration:{integration_id}',
    )
