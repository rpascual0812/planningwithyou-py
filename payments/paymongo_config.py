"""PayMongo Platforms: parent credentials and per-company child accounts."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from .models import PaymentIntegration


@dataclass(frozen=True)
class PayMongoPlatformConfig:
    """Parent (platform) secret key used for all PayMongo API calls."""

    secret_key: str
    webhook_secret: str
    platform_merchant_id: str


@dataclass(frozen=True)
class PayMongoCompanyContext:
    """Resolved PayMongo context when creating a payment for a company."""

    secret_key: str
    child_account_id: str
    platform_merchant_id: str
    platform_fee_bps: int


def platform_secret_key() -> str:
    """Parent platform secret API key (all PayMongo Platforms API calls)."""
    return (getattr(settings, 'PAYMONGO_SECRET_KEY', None) or '').strip()


def platform_webhook_secret() -> str:
    return (getattr(settings, 'PAYMONGO_WEBHOOK_SECRET', None) or '').strip()


def platform_merchant_id() -> str:
    return (getattr(settings, 'PAYMONGO_PLATFORM_MERCHANT_ID', None) or '').strip()


def get_platform_config() -> PayMongoPlatformConfig | None:
    secret_key = platform_secret_key()
    if not secret_key:
        return None
    return PayMongoPlatformConfig(
        secret_key=secret_key,
        webhook_secret=platform_webhook_secret(),
        platform_merchant_id=platform_merchant_id(),
    )


def get_company_paymongo_integration(company_id: int) -> PaymentIntegration | None:
    return PaymentIntegration.objects.filter(
        company_id=company_id,
        payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
    ).first()


def child_account_activated(integration: PaymentIntegration | None) -> bool:
    if integration is None:
        return False
    account_id = (integration.paymongo_account_id or '').strip()
    if not account_id:
        return False
    status = (integration.activation_status or '').strip().lower()
    return status in {'activated', 'active'}


def paymongo_configured(company_id: int | None = None) -> bool:
    """Platform parent key must be set; company may still need child onboarding."""
    return get_platform_config() is not None


def company_can_accept_paymongo_payments(company_id: int) -> bool:
    if not paymongo_configured(company_id):
        return False
    return child_account_activated(get_company_paymongo_integration(company_id))


def get_paymongo_company_context(company_id: int) -> PayMongoCompanyContext | None:
    platform = get_platform_config()
    integration = get_company_paymongo_integration(company_id)
    if platform is None or not child_account_activated(integration):
        return None
    assert integration is not None
    child_id = (integration.paymongo_account_id or '').strip()
    merchant_id = platform.platform_merchant_id
    if not child_id or not merchant_id:
        return None
    bps = int(getattr(settings, 'PAYMONGO_PLATFORM_FEE_BPS', 100) or 100)
    return PayMongoCompanyContext(
        secret_key=platform.secret_key,
        child_account_id=child_id,
        platform_merchant_id=merchant_id,
        platform_fee_bps=bps,
    )


def webhook_secrets_to_try(company_id: int | None) -> list[str]:
    """Platform webhook only (child accounts use parent webhook endpoint)."""
    secret = platform_webhook_secret()
    return [secret] if secret else []
