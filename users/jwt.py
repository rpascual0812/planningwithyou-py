"""JWT helpers for single active session per user."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

TOKEN_VERSION_CLAIM = 'token_version'
IMPERSONATION_CLAIM = 'impersonation'
IMPERSONATED_BY_CLAIM = 'impersonated_by'
IMPERSONATION_LOG_CLAIM = 'impersonation_log_id'
ACCOUNT_RESTRICTED_CODE = 'account_restricted'
ACCOUNT_RESTRICTED_MESSAGE = (
    'Your account access has been restricted. Please contact your administrator.'
)


def assert_user_not_account_restricted(user) -> None:
    if getattr(user, 'account_restricted', False):
        raise InvalidToken(
            {
                'detail': ACCOUNT_RESTRICTED_MESSAGE,
                'code': ACCOUNT_RESTRICTED_CODE,
            },
        )


class SessionRefreshToken(RefreshToken):
    """Refresh/access pair tagged with the user's current session generation."""

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token[TOKEN_VERSION_CLAIM] = user.token_version
        return token

    @classmethod
    def for_impersonation(cls, target_user, admin_user, log_id: int):
        """Issue tokens acting as *target_user* without invalidating their session."""
        token = cls.for_user(target_user)
        token[IMPERSONATION_CLAIM] = True
        token[IMPERSONATED_BY_CLAIM] = admin_user.pk
        token[IMPERSONATION_LOG_CLAIM] = log_id
        return token


def attach_impersonation_context(request, validated_token) -> None:
    if validated_token.get(IMPERSONATION_CLAIM):
        request.impersonated_by_id = validated_token.get(IMPERSONATED_BY_CLAIM)
        request.impersonation_log_id = validated_token.get(IMPERSONATION_LOG_CLAIM)
    else:
        request.impersonated_by_id = None
        request.impersonation_log_id = None


def is_impersonation_request(request) -> bool:
    return bool(getattr(request, 'impersonated_by_id', None))


class SessionJWTAuthentication(JWTAuthentication):
    """Reject access tokens from a previous login (other device/browser)."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        attach_impersonation_context(request, validated_token)
        return user, validated_token

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        assert_user_not_account_restricted(user)
        if validated_token.get(IMPERSONATION_CLAIM):
            user._impersonation_locked = True
            return user
        token_version = validated_token.get(TOKEN_VERSION_CLAIM, 0)
        if token_version != user.token_version:
            raise InvalidToken(
                {
                    'detail': 'This session was ended because you signed in elsewhere.',
                    'code': 'session_replaced',
                },
            )
        return user


class SessionTokenRefreshSerializer(TokenRefreshSerializer):
    """Reject refresh tokens from a previous login."""

    def validate(self, attrs):
        refresh = RefreshToken(attrs['refresh'])
        try:
            user_id = refresh[api_settings.USER_ID_CLAIM]
        except KeyError as exc:
            raise InvalidToken('Token contained no recognizable user identification') from exc

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist as exc:
            raise InvalidToken('User not found') from exc

        assert_user_not_account_restricted(user)

        if refresh.get(IMPERSONATION_CLAIM):
            self._validate_impersonation_refresh(refresh)
            return super(TokenRefreshSerializer, self).validate(attrs)

        if refresh.get(TOKEN_VERSION_CLAIM, 0) != user.token_version:
            raise InvalidToken(
                {
                    'detail': 'This session was ended because you signed in elsewhere.',
                    'code': 'session_replaced',
                },
            )

        return super().validate(attrs)

    def _validate_impersonation_refresh(self, refresh) -> None:
        from users.models import ImpersonationLog
        from users.roles import is_platform_admin

        admin_id = refresh.get(IMPERSONATED_BY_CLAIM)
        log_id = refresh.get(IMPERSONATION_LOG_CLAIM)
        if not admin_id or not log_id:
            raise InvalidToken('Invalid impersonation token.')

        try:
            admin = User.objects.get(pk=int(admin_id), deleted_at__isnull=True)
        except (User.DoesNotExist, TypeError, ValueError) as exc:
            raise InvalidToken('Impersonation admin not found.') from exc

        if not is_platform_admin(admin):
            raise InvalidToken('Impersonation admin no longer authorized.')

        log = ImpersonationLog.objects.filter(pk=int(log_id), ended_at__isnull=True).first()
        if log is None:
            raise InvalidToken('Impersonation session has ended.')


def blacklist_all_outstanding_tokens_for_user(user_id: int) -> None:
    """Invalidate existing refresh tokens stored in the blacklist tables."""
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    for outstanding in OutstandingToken.objects.filter(user_id=user_id):
        BlacklistedToken.objects.get_or_create(token=outstanding)


def blacklist_refresh_token_string(raw_refresh: str) -> None:
    try:
        refresh = RefreshToken(raw_refresh)
    except Exception:
        return
    refresh.blacklist()


def invalidate_user_session(user) -> None:
    """Revoke all JWTs for a user without issuing new tokens."""
    user.token_version = (user.token_version or 0) + 1
    user.save(update_fields=['token_version', 'updated_at'])
    blacklist_all_outstanding_tokens_for_user(user.pk)


def start_new_user_session(user) -> None:
    """
    Bump the user's session generation and revoke prior refresh tokens.
    Call immediately before issuing new JWTs on login or email verification.
    """
    invalidate_user_session(user)


def issue_tokens_for_user(user) -> dict[str, str]:
    from .serializers import user_may_login

    if not user_may_login(user):
        raise serializers.ValidationError(
            {
                'detail': (
                    ACCOUNT_RESTRICTED_MESSAGE
                    if getattr(user, 'account_restricted', False)
                    else 'No active account found with the given credentials.'
                ),
                'code': (
                    ACCOUNT_RESTRICTED_CODE
                    if getattr(user, 'account_restricted', False)
                    else 'no_active_account'
                ),
            },
        )
    start_new_user_session(user)
    refresh = SessionRefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def issue_impersonation_tokens(
    target_user,
    admin_user,
    log_id: int,
) -> dict[str, str]:
    refresh = SessionRefreshToken.for_impersonation(target_user, admin_user, log_id)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
