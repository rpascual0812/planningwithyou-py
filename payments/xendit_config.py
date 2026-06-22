"""Xendit xenPlatform settings for company KYB / sub-accounts."""

from __future__ import annotations

from django.conf import settings


def xendit_secret_key() -> str:
    return (getattr(settings, 'XENDIT_SECRET_KEY', None) or '').strip()


def xendit_platform_configured() -> bool:
    return bool(xendit_secret_key())


def xendit_onboarding_base_url() -> str:
    return (getattr(settings, 'XENDIT_ONBOARDING_URL', None) or '').strip()


def build_xendit_onboarding_url(account_id: str) -> str:
    """
    Build a hosted verification URL for a xenPlatform sub-account.

    ``XENDIT_ONBOARDING_URL`` may be a template containing ``{account_id}`` or a
    base path with the account id appended.
    """
    base = xendit_onboarding_base_url()
    aid = (account_id or '').strip()
    if not base or not aid:
        return ''
    if '{account_id}' in base:
        return base.format(account_id=aid)
    return f'{base.rstrip("/")}/{aid}'
