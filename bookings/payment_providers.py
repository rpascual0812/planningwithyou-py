"""Verified payment providers available for quotation payment links."""

from __future__ import annotations

from companies.kyb import provider_verification_payload
from companies.models import Company, CompanyKybVerification

from payments.paymongo_config import company_can_accept_paymongo_payments, paymongo_configured
from subscriptions.xendit_client import xendit_configured

PROVIDER_PAYMONGO = 'paymongo'
PROVIDER_XENDIT = 'xendit'
VALID_PROVIDERS = frozenset({PROVIDER_PAYMONGO, PROVIDER_XENDIT})

PROVIDER_LABELS = {
    PROVIDER_PAYMONGO: 'PayMongo',
    PROVIDER_XENDIT: 'Xendit',
}


def _kyb_for_company(company: Company) -> CompanyKybVerification | None:
    return getattr(company, 'kyb_verification', None)


def paymongo_kyb_verified(kyb: CompanyKybVerification | None) -> bool:
    return (
        kyb is not None
        and kyb.paymongo_status == CompanyKybVerification.PaymongoStatus.APPROVED
    )


def xendit_kyb_verified(kyb: CompanyKybVerification | None) -> bool:
    return (
        kyb is not None
        and kyb.xendit_status == CompanyKybVerification.XenditStatus.APPROVED
    )


def paymongo_link_ready(company: Company) -> bool:
    kyb = _kyb_for_company(company)
    return (
        paymongo_kyb_verified(kyb)
        and paymongo_configured(company.pk)
        and company_can_accept_paymongo_payments(company.pk)
    )


def xendit_link_ready(company: Company) -> bool:
    kyb = _kyb_for_company(company)
    return (
        xendit_kyb_verified(kyb)
        and xendit_configured()
        and bool((kyb.xendit_account_id or '').strip())
    )


def verified_payment_providers(company: Company) -> list[dict[str, str]]:
    """Providers with approved business verification (KYB) for payment link selection."""
    kyb = _kyb_for_company(company)
    options: list[dict[str, str]] = []
    if paymongo_kyb_verified(kyb):
        options.append(
            {
                'provider': PROVIDER_PAYMONGO,
                'label': PROVIDER_LABELS[PROVIDER_PAYMONGO],
            },
        )
    if xendit_kyb_verified(kyb):
        options.append(
            {
                'provider': PROVIDER_XENDIT,
                'label': PROVIDER_LABELS[PROVIDER_XENDIT],
            },
        )
    return options


def link_ready_payment_providers(company: Company) -> list[dict[str, str]]:
    """Providers verified and fully configured to create a payment link right now."""
    options: list[dict[str, str]] = []
    if paymongo_link_ready(company):
        options.append(
            {
                'provider': PROVIDER_PAYMONGO,
                'label': PROVIDER_LABELS[PROVIDER_PAYMONGO],
            },
        )
    if xendit_link_ready(company):
        options.append(
            {
                'provider': PROVIDER_XENDIT,
                'label': PROVIDER_LABELS[PROVIDER_XENDIT],
            },
        )
    return options


def normalize_payment_provider(raw: str | None, *, company: Company) -> str:
    provider = (raw or '').strip().lower()
    available = {item['provider'] for item in verified_payment_providers(company)}
    if not available:
        raise ValueError('No verified payment providers are available for this company.')
    if provider in available:
        return provider
    if not provider and len(available) == 1:
        return next(iter(available))
    if not provider:
        raise ValueError('Select a payment provider.')
    raise ValueError(
        f'Payment provider "{provider}" is not verified for this company.',
    )


def assert_payment_provider_link_ready(company: Company, provider: str) -> None:
    if provider == PROVIDER_PAYMONGO and not paymongo_link_ready(company):
        raise ValueError(
            'PayMongo is not ready for payment links. Complete PayMongo integration '
            'under Company Settings.',
        )
    if provider == PROVIDER_XENDIT and not xendit_link_ready(company):
        raise ValueError(
            'Xendit is not ready for payment links. Complete Xendit business verification first.',
        )


def provider_verifications_summary(company: Company) -> dict:
    kyb = _kyb_for_company(company)
    if kyb is None:
        return {
            'verified_payment_providers': [],
            'provider_verifications': None,
        }
    return {
        'verified_payment_providers': verified_payment_providers(company),
        'provider_verifications': provider_verification_payload(kyb),
    }
