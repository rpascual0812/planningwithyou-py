"""Create PayMongo merchants and onboarding links from company KYB applications."""

from __future__ import annotations

from django.utils import timezone

from companies.kyb import missing_kyb_application_fields, paymongo_business_type
from companies.models import Company, CompanyKybVerification

from bookings.paymongo_client import PayMongoError

from .models import PaymentIntegration
from .paymongo_config import get_platform_config
from .paymongo_onboarding import PayMongoOnboardingError, _paymongo_onboarding_error
from .paymongo_platform_client import (
    _resource_id,
    create_child_merchant_account,
    create_identity_verification_session,
    create_merchant_onboarding_link,
    create_platform_merchant,
    get_child_account,
    verification_session_url,
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


def _merchant_id_from_v1_resource(data: dict) -> str:
    return _resource_id(data)


def _merchant_id_from_v2_account(data: dict) -> str:
    return _resource_id(data)


def _create_onboarding_url_v1(merchant_id: str) -> str:
    return create_merchant_onboarding_link(merchant_id)


def _create_onboarding_url_v2(account_id: str) -> str:
    session = create_identity_verification_session(account_id)
    return verification_session_url(session)


def start_paymongo_merchant_onboarding(
    company: Company,
    *,
    created_by=None,
    regenerate_link: bool = False,
) -> CompanyKybVerification:
    """
    Create (or reuse) a PayMongo merchant, generate an onboarding link, and
    persist ids/urls on the company KYB record and payment integration.
    """
    if get_platform_config() is None:
        raise PayMongoOnboardingError('PayMongo platform is not configured on the server.')

    kyb = _get_or_create_kyb(company)
    missing = missing_kyb_application_fields(kyb)
    if missing:
        raise PayMongoOnboardingError(
            f'Missing required fields: {", ".join(missing)}.',
        )

    integration = _get_or_create_integration(company, created_by=created_by)
    merchant_id = (kyb.paymongo_merchant_id or integration.paymongo_account_id or '').strip()

    if not merchant_id:
        business_name = (kyb.merchant_business_name or company.name).strip()
        email = kyb.merchant_email.strip()
        mobile = kyb.merchant_mobile_number.strip()
        pm_type = paymongo_business_type(kyb.business_type)
        try:
            merchant = create_platform_merchant(
                business_name=business_name,
                business_type=pm_type,
                email=email,
                mobile_number=mobile,
            )
            merchant_id = _merchant_id_from_v1_resource(merchant)
        except PayMongoError as exc:
            if exc.status_code not in {404, 405}:
                raise _paymongo_onboarding_error(exc) from exc
            try:
                account = create_child_merchant_account()
                merchant_id = _merchant_id_from_v2_account(account)
            except PayMongoError as exc2:
                raise _paymongo_onboarding_error(exc2) from exc2

        kyb.paymongo_merchant_id = merchant_id
        integration.paymongo_account_id = merchant_id
        integration.activation_status = 'pending'
        integration.save(
            update_fields=['paymongo_account_id', 'activation_status', 'updated_at'],
        )
        kyb.save(update_fields=['paymongo_merchant_id', 'updated_at'])

    onboarding_url = (kyb.onboarding_url or integration.identity_verification_url or '').strip()
    if regenerate_link or not onboarding_url:
        try:
            onboarding_url = _create_onboarding_url_v1(merchant_id)
        except PayMongoError as exc:
            if exc.status_code not in {404, 405}:
                already_done = exc.status_code == 400 and 'already been completed' in str(exc).lower()
                if not already_done:
                    raise _paymongo_onboarding_error(exc) from exc
                onboarding_url = ''
            else:
                try:
                    onboarding_url = _create_onboarding_url_v2(merchant_id)
                except PayMongoError as exc2:
                    already_done = (
                        exc2.status_code == 400
                        and 'already been completed' in str(exc2).lower()
                    )
                    if not already_done:
                        raise _paymongo_onboarding_error(exc2) from exc2
                    onboarding_url = ''

        if onboarding_url:
            kyb.onboarding_url = onboarding_url
            integration.identity_verification_url = onboarding_url
            kyb.save(update_fields=['onboarding_url', 'updated_at'])
            integration.save(
                update_fields=['identity_verification_url', 'updated_at'],
            )

    kyb.status = CompanyKybVerification.Status.PENDING_PAYMONGO
    if not kyb.submitted_at:
        kyb.submitted_at = timezone.now()
    kyb.save(update_fields=['status', 'submitted_at', 'updated_at'])

    # Best-effort sync activation fields from v2 account API when available.
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

    return kyb
