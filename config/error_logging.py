"""Persist unhandled request errors to ``error_logs``."""

from __future__ import annotations

import logging
import traceback

from django.http import HttpRequest

from .models import ErrorLog

logger = logging.getLogger(__name__)

MAX_BODY_CHARS = 8192
SENSITIVE_PATH_FRAGMENTS = (
    '/login',
    '/register',
    '/password',
    '/token',
    '/refresh',
)

__all__ = ['log_request_error']


def _client_ip(request: HttpRequest) -> str | None:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip() or None
    return request.META.get('REMOTE_ADDR')


def _safe_request_body(request: HttpRequest) -> str:
    path = request.path.lower()
    if any(fragment in path for fragment in SENSITIVE_PATH_FRAGMENTS):
        return ''

    try:
        raw = request.body
    except Exception:
        return ''

    if not raw:
        return ''

    try:
        text = raw.decode('utf-8', errors='replace')
    except Exception:
        return '[binary body]'

    if len(text) > MAX_BODY_CHARS:
        return f'{text[:MAX_BODY_CHARS]}… [truncated]'
    return text


def _format_traceback(exc: BaseException | None) -> str:
    if exc is None:
        return ''
    return ''.join(
        traceback.format_exception(type(exc), exc, exc.__traceback__),
    )


def log_request_error(
    request: HttpRequest | None,
    *,
    exception: BaseException | None = None,
    status_code: int | None = None,
    account_id: int | None = None,
    user_id: int | None = None,
) -> ErrorLog | None:
    """Write an error row. Never raises — logging must not break responses."""
    if request is None:
        return None

    user = getattr(request, 'user', None)
    resolved_user_id = user_id
    if resolved_user_id is None and getattr(user, 'is_authenticated', False):
        resolved_user_id = user.pk
    resolved_account_id = account_id
    if resolved_account_id is None and resolved_user_id:
        resolved_account_id = getattr(user, 'account_id', None)

    exc_type = type(exception).__name__ if exception else ''
    exc_message = str(exception) if exception else ''

    try:
        return ErrorLog.objects.create(
            method=(request.method or '')[:16],
            path=request.path or '',
            query_string=request.META.get('QUERY_STRING', '')[:2048],
            status_code=status_code,
            exception_type=exc_type[:255],
            exception_message=exc_message,
            traceback=_format_traceback(exception),
            request_body=_safe_request_body(request),
            user_id=resolved_user_id,
            account_id=resolved_account_id,
            ip_address=_client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:1024],
        )
    except Exception:
        logger.exception('Failed to persist error_logs row for %s', request.path)
        return None
