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


class SessionJWTAuthentication(JWTAuthentication):
    """Reject access tokens from a previous login (other device/browser)."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        assert_user_not_account_restricted(user)
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

        if refresh.get(TOKEN_VERSION_CLAIM, 0) != user.token_version:
            raise InvalidToken(
                {
                    'detail': 'This session was ended because you signed in elsewhere.',
                    'code': 'session_replaced',
                },
            )

        return super().validate(attrs)


def blacklist_all_outstanding_tokens_for_user(user_id: int) -> None:
    """Invalidate existing refresh tokens stored in the blacklist tables."""
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    for outstanding in OutstandingToken.objects.filter(user_id=user_id):
        BlacklistedToken.objects.get_or_create(token=outstanding)


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
