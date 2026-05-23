"""Resolve PayMongo credentials per company or platform defaults."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from .models import PaymentIntegration


@dataclass(frozen=True)
class PayMongoConfig:
    secret_key: str
    webhook_secret: str
    uses_platform_defaults: bool


def get_company_paymongo_integration(company_id: int) -> PaymentIntegration | None:
    return (
        PaymentIntegration.objects.filter(
            company_id=company_id,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
        )
        .first()
    )


def get_paymongo_config(company_id: int | None) -> PayMongoConfig | None:
    """
    Company-specific integration when configured; otherwise platform env keys.
    """
    if company_id is not None:
        integration = get_company_paymongo_integration(company_id)
        if integration is not None:
            secret_key = (integration.key or '').strip()
            if secret_key:
                return PayMongoConfig(
                    secret_key=secret_key,
                    webhook_secret=(integration.secret or '').strip(),
                    uses_platform_defaults=False,
                )

    secret_key = (getattr(settings, 'PAYMONGO_SECRET_KEY', None) or '').strip()
    if not secret_key:
        return None
    webhook_secret = (getattr(settings, 'PAYMONGO_WEBHOOK_SECRET', None) or '').strip()
    return PayMongoConfig(
        secret_key=secret_key,
        webhook_secret=webhook_secret,
        uses_platform_defaults=True,
    )


def paymongo_configured(company_id: int | None = None) -> bool:
    cfg = get_paymongo_config(company_id)
    return cfg is not None and bool(cfg.secret_key)


def webhook_secrets_to_try(company_id: int | None) -> list[str]:
    """Webhook signing secrets to try (company custom, then platform)."""
    seen: set[str] = set()
    out: list[str] = []

    def add(secret: str) -> None:
        s = (secret or '').strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    if company_id is not None:
        integration = get_company_paymongo_integration(company_id)
        if integration is not None and (integration.key or '').strip():
            add(integration.secret)

    add(getattr(settings, 'PAYMONGO_WEBHOOK_SECRET', None) or '')
    return out
