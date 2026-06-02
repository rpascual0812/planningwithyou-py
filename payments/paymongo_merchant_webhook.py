"""Apply PayMongo merchant.* and account.* platform webhooks to company KYB records."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from companies.kyb_notifications import send_company_kyb_approved_email
from companies.models import CompanyKybVerification

from .models import PaymentIntegration
from .paymongo_onboarding import refresh_paymongo_integration

logger = logging.getLogger(__name__)

_MERCHANT_EVENT_PREFIX = 'merchant.'
_ACCOUNT_EVENT_PREFIX = 'account.'

_ACTIVATION_EVENT_TYPES = frozenset({
    'merchant.verified',
    'merchant.activated',
    'account.activated',
    'account.registration.activated',
    'account.registration.completed',
})

_REJECTION_EVENT_TYPES = frozenset({
    'merchant.rejected',
    'merchant.declined',
    'account.rejected',
    'account.declined',
})

_PENDING_EVENT_TYPES = frozenset({
    'merchant.pending',
    'merchant.submitted',
    'account.pending',
    'account.submitted',
    'account.registration.pending',
})


def _normalized_event_type(event: dict) -> str:
    event_type = (event.get('type') or '').strip().lower()
    if event_type:
        return event_type
    data = event.get('data')
    if not isinstance(data, dict):
        return ''
    attrs = data.get('attributes')
    if isinstance(attrs, dict):
        nested_type = (attrs.get('type') or '').strip().lower()
        if nested_type:
            return nested_type
    return ''


def _is_child_account_platform_event(event_type: str) -> bool:
    return event_type.startswith(_MERCHANT_EVENT_PREFIX) or event_type.startswith(
        _ACCOUNT_EVENT_PREFIX,
    )


def _resource_id_from_event(event: dict) -> str:
    data = event.get('data')
    if not isinstance(data, dict):
        return ''

    attrs = data.get('attributes')
    if isinstance(attrs, dict):
        resource = attrs.get('data')
        if isinstance(resource, dict):
            rid = str(resource.get('id') or '').strip()
            if rid:
                return rid

    resource = data.get('id')
    if resource:
        return str(resource).strip()
    return ''


def _nested_account_attributes(event: dict) -> dict:
    data = event.get('data')
    if not isinstance(data, dict):
        return {}
    attrs = data.get('attributes')
    if not isinstance(attrs, dict):
        return {}
    resource = attrs.get('data')
    if isinstance(resource, dict):
        resource_attrs = resource.get('attributes')
        if isinstance(resource_attrs, dict):
            return resource_attrs
        return resource
    return attrs


def _event_indicates_activation(event: dict, event_type: str) -> bool:
    if event_type in _ACTIVATION_EVENT_TYPES:
        return True
    nested = _nested_account_attributes(event)
    activation = str(nested.get('activation_status') or '').strip().lower()
    if activation in {'activated', 'active'}:
        return True
    status = str(nested.get('status') or '').strip().lower()
    return status in {'verified', 'activated', 'active', 'approved'}


def _find_kyb_by_merchant_id(merchant_id: str) -> CompanyKybVerification | None:
    if not merchant_id:
        return None
    return (
        CompanyKybVerification.objects.select_related('company', 'company__account')
        .filter(paymongo_merchant_id=merchant_id)
        .first()
    )


def _find_integration_by_merchant_id(merchant_id: str) -> PaymentIntegration | None:
    if not merchant_id:
        return None
    return PaymentIntegration.objects.filter(
        paymongo_account_id=merchant_id,
        payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
    ).first()


def _resolve_kyb_for_webhook(resource_id: str) -> CompanyKybVerification | None:
    kyb = _find_kyb_by_merchant_id(resource_id)
    if kyb is not None:
        return kyb
    if not resource_id:
        return None
    integration = _find_integration_by_merchant_id(resource_id)
    if integration is None:
        return None
    return CompanyKybVerification.objects.select_related(
        'company',
        'company__account',
    ).filter(company_id=integration.company_id).first()


@transaction.atomic
def _mark_kyb_verified(kyb: CompanyKybVerification) -> None:
    now = timezone.now()
    kyb.status = CompanyKybVerification.Status.APPROVED
    kyb.reviewed_at = now
    kyb.rejection_notes = ''
    kyb.save(
        update_fields=['status', 'reviewed_at', 'rejection_notes', 'updated_at'],
    )


@transaction.atomic
def _mark_kyb_rejected(kyb: CompanyKybVerification, *, reason: str = '') -> None:
    now = timezone.now()
    kyb.status = CompanyKybVerification.Status.REJECTED
    kyb.reviewed_at = now
    if reason:
        kyb.rejection_notes = reason[:4000]
    kyb.save(
        update_fields=['status', 'reviewed_at', 'rejection_notes', 'updated_at'],
    )


@transaction.atomic
def _mark_kyb_pending(kyb: CompanyKybVerification) -> None:
    if kyb.status == CompanyKybVerification.Status.APPROVED:
        return
    kyb.status = CompanyKybVerification.Status.PENDING_PAYMONGO
    kyb.save(update_fields=['status', 'updated_at'])


def _sync_integration_after_webhook(
    kyb: CompanyKybVerification,
    resource_id: str,
    *,
    force_activated: bool = False,
) -> None:
    lookup_id = (kyb.paymongo_merchant_id or resource_id or '').strip()
    integration = _find_integration_by_merchant_id(lookup_id)
    if integration is None:
        return
    try:
        refresh_paymongo_integration(integration)
        integration.refresh_from_db()
    except Exception:
        logger.exception('Failed to refresh PayMongo integration after child account webhook')
    if force_activated:
        PaymentIntegration.objects.filter(pk=integration.pk).update(
            activation_status='activated',
        )


def _handle_child_account_activation(
    kyb: CompanyKybVerification,
    resource_id: str,
) -> None:
    prior_status = kyb.status
    _mark_kyb_verified(kyb)
    _sync_integration_after_webhook(kyb, resource_id, force_activated=True)
    if prior_status != CompanyKybVerification.Status.APPROVED:
        company_id = kyb.company_id
        transaction.on_commit(
            lambda cid=company_id: send_company_kyb_approved_email(cid),
        )


def handle_paymongo_merchant_webhook_event(event: dict) -> bool:
    """
    Return True if this event was handled as a PayMongo child merchant/account event.

    On activation/registration success: updates ``company_kyb_verifications``,
    sets ``companies.kyb_verified``, syncs ``payment_integrations.activation_status``,
    and emails ``companies.contact_email``.
    """
    event_type = _normalized_event_type(event)
    if not _is_child_account_platform_event(event_type):
        return False

    resource_id = _resource_id_from_event(event)
    kyb = _resolve_kyb_for_webhook(resource_id)
    if kyb is None:
        logger.info(
            'PayMongo child account webhook ignored: no KYB for resource %s (type=%s)',
            resource_id,
            event_type,
        )
        return True

    if _event_indicates_activation(event, event_type):
        _handle_child_account_activation(kyb, resource_id)
    elif event_type in _REJECTION_EVENT_TYPES:
        attrs = event.get('data', {}).get('attributes', {})
        reason = ''
        if isinstance(attrs, dict):
            reason = str(attrs.get('rejection_reason') or attrs.get('reason') or '')
        _mark_kyb_rejected(kyb, reason=reason)
        _sync_integration_after_webhook(kyb, resource_id)
    elif event_type in _PENDING_EVENT_TYPES:
        _mark_kyb_pending(kyb)
        _sync_integration_after_webhook(kyb, resource_id)
    else:
        logger.info('Unhandled PayMongo child account event type: %s', event_type)
        _sync_integration_after_webhook(kyb, resource_id)

    return True
