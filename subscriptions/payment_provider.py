"""Platform subscription billing payment provider (PayMongo or Xendit)."""

from __future__ import annotations

from django.conf import settings

from system_settings.models import SystemSetting

SUBSCRIPTION_PAYMENT_PROVIDER_KEY = 'subscription_payment_provider'
PROVIDER_PAYMONGO = 'paymongo'
PROVIDER_XENDIT = 'xendit'
DEFAULT_PROVIDER = PROVIDER_PAYMONGO
VALID_PROVIDERS = frozenset({PROVIDER_PAYMONGO, PROVIDER_XENDIT})

PROVIDER_LABELS = {
    PROVIDER_PAYMONGO: 'PayMongo',
    PROVIDER_XENDIT: 'Xendit',
}


def paymongo_configured() -> bool:
    from bookings.paymongo_client import paymongo_configured as _configured

    return _configured()


def xendit_configured() -> bool:
    return bool(getattr(settings, 'XENDIT_SECRET_KEY', '').strip())


def provider_configured(provider: str) -> bool:
    if provider == PROVIDER_PAYMONGO:
        return paymongo_configured()
    if provider == PROVIDER_XENDIT:
        return xendit_configured()
    return False


def active_subscription_payment_provider() -> str:
    row = SystemSetting.objects.filter(name=SUBSCRIPTION_PAYMENT_PROVIDER_KEY).first()
    if row is None:
        return DEFAULT_PROVIDER
    value = (row.value or '').strip().lower()
    if value in VALID_PROVIDERS:
        return value
    return DEFAULT_PROVIDER


def set_subscription_payment_provider(provider: str) -> str:
    normalized = (provider or '').strip().lower()
    if normalized not in VALID_PROVIDERS:
        raise ValueError(f'Invalid subscription payment provider: {provider}')
    SystemSetting.objects.update_or_create(
        name=SUBSCRIPTION_PAYMENT_PROVIDER_KEY,
        defaults={'value': normalized},
    )
    return normalized


def provider_status_payload() -> dict:
    provider = active_subscription_payment_provider()
    return {
        'provider': provider,
        'provider_label': PROVIDER_LABELS.get(provider, provider.title()),
        'paymongo_configured': paymongo_configured(),
        'xendit_configured': xendit_configured(),
        'configured': provider_configured(provider),
    }
