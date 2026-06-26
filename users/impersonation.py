from __future__ import annotations

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from users.models import ImpersonationLog, User
from users.roles import is_platform_admin
from users.serializers import user_may_login

from .jwt import issue_impersonation_tokens


def _client_ip(request) -> str | None:
    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    if forwarded:
        return forwarded
    return request.META.get('REMOTE_ADDR')


def start_impersonation(*, admin_user, target_user_id: int, request) -> dict:
    if not is_platform_admin(admin_user):
        raise PermissionDenied('Platform admin access required.')

    if getattr(request, 'impersonated_by_id', None):
        raise ValidationError({'detail': 'Already impersonating a user.'})

    if int(target_user_id) == admin_user.pk:
        raise ValidationError({'detail': 'Cannot impersonate yourself.'})

    target = (
        User.objects.filter(pk=target_user_id, deleted_at__isnull=True)
        .select_related('account', 'company')
        .first()
    )
    if target is None:
        raise ValidationError({'user_id': ['User not found.']})

    if not user_may_login(target):
        raise ValidationError({'user_id': ['Target user cannot log in.']})

    log = ImpersonationLog.objects.create(
        admin_user=admin_user,
        target_user=target,
        account_id=target.account_id,
        company_id=target.company_id,
        ip_address=_client_ip(request),
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:2000],
    )
    tokens = issue_impersonation_tokens(target, admin_user, log.pk)
    return {
        **tokens,
        'impersonation_log_id': log.pk,
        'target_user_id': target.pk,
    }


def end_impersonation(*, request, refresh_token: str = '') -> None:
    log_id = getattr(request, 'impersonation_log_id', None)
    if log_id:
        ImpersonationLog.objects.filter(pk=log_id, ended_at__isnull=True).update(
            ended_at=timezone.now(),
        )
    elif refresh_token:
        from rest_framework_simplejwt.tokens import RefreshToken

        try:
            refresh = RefreshToken(refresh_token)
            log_id = refresh.get('impersonation_log_id')
            if log_id:
                ImpersonationLog.objects.filter(pk=log_id, ended_at__isnull=True).update(
                    ended_at=timezone.now(),
                )
        except Exception:
            pass

    if refresh_token:
        from .jwt import blacklist_refresh_token_string

        blacklist_refresh_token_string(refresh_token)
