"""Create PayMongo merchants and onboarding links from company KYB applications."""

from __future__ import annotations

from django.utils import timezone

from companies.kyb import missing_kyb_application_fields, paymongo_business_type
from companies.models import Company, CompanyKybVerification

from bookings.paymongo_client import PayMongoError

from .models import PaymentIntegration
from .paymongo_config import (
    build_paymongo_onboarding_url,
    get_platform_config,
    paymongo_onboarding_base_url,
)
from .paymongo_onboarding import PayMongoOnboardingError, _paymongo_onboarding_error
from .paymongo_platform_client import (
    _resource_id,
    create_child_merchant,
    get_child_account,
)


def _get_or_create_kyb(company: Company) -> CompanyKybVerification:
    kyb, _ = CompanyKybVerification.objects.get_or_create(company=company)
    return kyb


def _get_or_create_integration(company: Company, *, created_by=None) -> PaymentIntegration:
    integration = (
        PaymentIntegration.all_objects.filter(
            company_id=company.pk,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
        )
        .order_by('-id')
        .first()
    )
    if integration is None:
        integration = PaymentIntegration(
            company=company,
            account_id=company.account_id,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
            created_by=created_by,
            activation_status='not_started',
        )
        integration.save()
    else:
        integration.deleted_at = None
        integration.save(update_fields=['deleted_at', 'updated_at'])
    return integration


def _create_paymongo_merchant(kyb: CompanyKybVerification, company: Company) -> str:
    """Always provision a new PayMongo merchant using the KYB application fields."""
    business_name = (kyb.merchant_business_name or company.name).strip()
    email = kyb.merchant_email.strip()
    mobile = kyb.merchant_mobile_number.strip()
    pm_type = paymongo_business_type(kyb.business_type)
    try:
        merchant = create_child_merchant(
            trade_name=business_name,
            business_type=pm_type,
            email=email,
            phone_number=mobile,
        )
        return _resource_id(merchant)
    except PayMongoError as exc:
        raise _paymongo_onboarding_error(exc) from exc


def start_paymongo_merchant_onboarding(
    company: Company,
    *,
    created_by=None,
    regenerate_link: bool = False,
) -> CompanyKybVerification:
    """
    Create a new PayMongo merchant from the KYB form, build the hosted onboarding
    URL from ``PAYMONGO_ONBOARDING_URL``, and persist ids on KYB + integration.

    ``regenerate_link`` is accepted for API compatibility; each call still creates
    a new merchant (retry / open again).
    """
    del regenerate_link  # always create a fresh merchant

    if get_platform_config() is None:
        raise PayMongoOnboardingError('PayMongo platform is not configured on the server.')

    if not paymongo_onboarding_base_url():
        raise PayMongoOnboardingError('PAYMONGO_ONBOARDING_URL is not configured on the server.')

    kyb = _get_or_create_kyb(company)
    missing = missing_kyb_application_fields(kyb)
    if missing:
        raise PayMongoOnboardingError(
            f'Missing required fields: {", ".join(missing)}.',
        )

    integration = _get_or_create_integration(company, created_by=created_by)
    merchant_id = _create_paymongo_merchant(kyb, company)
    onboarding_url = build_paymongo_onboarding_url(merchant_id)

    kyb.paymongo_merchant_id = merchant_id
    kyb.onboarding_url = onboarding_url
    kyb.status = CompanyKybVerification.Status.PENDING_PAYMONGO
    if not kyb.submitted_at:
        kyb.submitted_at = timezone.now()
    kyb.save(
        update_fields=[
            'paymongo_merchant_id',
            'onboarding_url',
            'status',
            'submitted_at',
            'updated_at',
        ],
    )

    integration.paymongo_account_id = merchant_id
    integration.identity_verification_url = onboarding_url
    integration.activation_status = 'pending'
    integration.save(
        update_fields=[
            'paymongo_account_id',
            'identity_verification_url',
            'activation_status',
            'updated_at',
        ],
    )

    try:
        account = get_child_account(merchant_id)
        integration.activation_status = str(
            account.get('activation_status') or integration.activation_status or 'pending',
        )
        person = account.get('person') if isinstance(account.get('person'), dict) else {}
        integration.identity_verification_status = str(
            person.get('identity_verification_status') or '',
        )
        integration.api_response = account
        integration.save(
            update_fields=[
                'activation_status',
                'identity_verification_status',
                'api_response',
                'updated_at',
            ],
        )
    except PayMongoError:
        pass

    kyb.refresh_from_db()
    return kyb
