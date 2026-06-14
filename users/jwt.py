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


def start_new_user_session(user) -> None:
    """
    Bump the user's session generation and revoke prior refresh tokens.
    Call immediately before issuing new JWTs on login or email verification.
    """
    user.token_version = (user.token_version or 0) + 1
    user.save(update_fields=['token_version', 'updated_at'])
    blacklist_all_outstanding_tokens_for_user(user.pk)


def issue_tokens_for_user(user) -> dict[str, str]:
    start_new_user_session(user)
    refresh = SessionRefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
