"""Start and sync PayMongo Platforms child accounts for companies."""

from __future__ import annotations

from django.utils import timezone

from companies.models import Company

from .models import PaymentIntegration
from .paymongo_config import get_platform_config
from bookings.paymongo_client import PayMongoError

from .paymongo_platform_client import (
    activate_child_account,
    create_child_merchant_account,
    create_identity_verification_session,
    get_child_account,
    verification_session_url,
)


class PayMongoOnboardingError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _person_from_account(account: dict) -> dict:
    person = account.get('person')
    return person if isinstance(person, dict) else {}


def _sync_integration_from_account(
    integration: PaymentIntegration,
    account: dict,
) -> PaymentIntegration:
    integration.paymongo_account_id = str(account.get('id') or integration.paymongo_account_id)
    integration.activation_status = str(
        account.get('activation_status') or integration.activation_status or 'pending',
    )
    person = _person_from_account(account)
    integration.identity_verification_status = str(
        person.get('identity_verification_status') or '',
    )
    integration.api_response = account
    integration.save(
        update_fields=[
            'paymongo_account_id',
            'activation_status',
            'identity_verification_status',
            'api_response',
            'updated_at',
        ],
    )
    return integration


def _reset_paymongo_child(integration: PaymentIntegration) -> PaymentIntegration:
    """Clear linked PayMongo child account (e.g. after disconnect or stale test id)."""
    integration.paymongo_account_id = ''
    integration.activation_status = 'not_started'
    integration.identity_verification_status = ''
    integration.identity_verification_url = ''
    integration.api_response = None
    integration.save(
        update_fields=[
            'paymongo_account_id',
            'activation_status',
            'identity_verification_status',
            'identity_verification_url',
            'api_response',
            'updated_at',
        ],
    )
    return integration


def _paymongo_onboarding_error(exc: PayMongoError) -> PayMongoOnboardingError:
    msg = str(exc)
    if exc.status_code == 404:
        msg = (
            'PayMongo could not find this linked account. It may be from test mode '
            'while live keys are configured. Disconnect and connect again.'
        )
    elif exc.status_code == 403:
        msg = (
            'Your PayMongo account cannot create child accounts yet. '
            'Contact support@paymongo.com to enable PayMongo Platforms.'
        )
    return PayMongoOnboardingError(msg, status_code=exc.status_code, payload=exc.payload)


def refresh_paymongo_integration(integration: PaymentIntegration) -> PaymentIntegration:
    account_id = (integration.paymongo_account_id or '').strip()
    if not account_id:
        return integration
    try:
        account = get_child_account(account_id)
    except PayMongoError as exc:
        if exc.status_code == 404:
            return _reset_paymongo_child(integration)
        raise _paymongo_onboarding_error(exc) from exc
    return _sync_integration_from_account(integration, account)


def start_paymongo_onboarding(
    company: Company,
    *,
    created_by=None,
) -> PaymentIntegration:
    if get_platform_config() is None:
        raise PayMongoOnboardingError('PayMongo platform is not configured on the server.')

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

    account_id = (integration.paymongo_account_id or '').strip()
    if account_id:
        try:
            account = get_child_account(account_id)
            _sync_integration_from_account(integration, account)
        except PayMongoError as exc:
            if exc.status_code == 404:
                integration = _reset_paymongo_child(integration)
                account_id = ''
            else:
                raise _paymongo_onboarding_error(exc) from exc

    if not account_id:
        try:
            account = create_child_merchant_account()
        except PayMongoError as exc:
            raise _paymongo_onboarding_error(exc) from exc
        _sync_integration_from_account(integration, account)
        account_id = integration.paymongo_account_id

    identity_status = (integration.identity_verification_status or '').strip().lower()
    if identity_status not in {'passed', 'verified'}:
        existing_url = (integration.identity_verification_url or '').strip()
        if not existing_url:
            try:
                id_session = create_identity_verification_session(account_id)
                url = verification_session_url(id_session)
                if url:
                    integration.identity_verification_url = url
                    integration.save(
                        update_fields=['identity_verification_url', 'updated_at'],
                    )
            except PayMongoError as exc:
                already_done = exc.status_code == 400 and 'already been completed' in str(exc).lower()
                if not already_done:
                    raise _paymongo_onboarding_error(exc) from exc

    integration = refresh_paymongo_integration(integration)

    activation = (integration.activation_status or '').strip().lower()
    identity = (integration.identity_verification_status or '').strip().lower()
    if activation not in {'activated', 'active'} and identity in {'passed', 'verified'}:
        try:
            account = activate_child_account(account_id)
            _sync_integration_from_account(integration, account)
        except PayMongoError:
            integration.activation_status = 'pending_activation'
            integration.save(update_fields=['activation_status', 'updated_at'])

    return integration


def disconnect_paymongo_integration(company_id: int) -> None:
    integration = PaymentIntegration.all_objects.filter(
        company_id=company_id,
        payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
    ).first()
    if integration is None:
        return
    _reset_paymongo_child(integration)
    integration.deleted_at = timezone.now()
    integration.save(update_fields=['deleted_at', 'updated_at'])
