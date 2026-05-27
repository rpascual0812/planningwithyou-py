"""Apply PayMongo merchant.* platform webhook events to company KYB records."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from companies.models import CompanyKybVerification

from .models import PaymentIntegration
from .paymongo_onboarding import refresh_paymongo_integration

logger = logging.getLogger(__name__)

_MERCHANT_EVENT_PREFIX = 'merchant.'


def _merchant_id_from_event(event: dict) -> str:
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


def _find_kyb_by_merchant_id(merchant_id: str) -> CompanyKybVerification | None:
    if not merchant_id:
        return None
    return (
        CompanyKybVerification.objects.select_related('company')
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


def handle_paymongo_merchant_webhook_event(event: dict) -> bool:
    """Return True if this event was handled as a merchant platform event."""
    event_type = (event.get('type') or '').strip().lower()
    if not event_type.startswith(_MERCHANT_EVENT_PREFIX):
        data = event.get('data')
        if isinstance(data, dict):
            attrs = data.get('attributes')
            if isinstance(attrs, dict):
                event_type = (attrs.get('type') or event_type).strip().lower()
    if not event_type.startswith(_MERCHANT_EVENT_PREFIX):
        return False

    merchant_id = _merchant_id_from_event(event)
    kyb = _find_kyb_by_merchant_id(merchant_id)
    if kyb is None and merchant_id:
        integration = _find_integration_by_merchant_id(merchant_id)
        if integration is not None:
            kyb = CompanyKybVerification.objects.filter(
                company_id=integration.company_id,
            ).first()

    if kyb is None:
        logger.info('PayMongo merchant webhook ignored: no KYB for merchant %s', merchant_id)
        return True

    integration = _find_integration_by_merchant_id(
        (kyb.paymongo_merchant_id or merchant_id or '').strip(),
    )
    if integration is not None:
        try:
            refresh_paymongo_integration(integration)
        except Exception:
            logger.exception('Failed to refresh PayMongo integration after merchant webhook')

    if event_type in {'merchant.verified', 'merchant.activated'}:
        _mark_kyb_verified(kyb)
    elif event_type in {'merchant.rejected', 'merchant.declined'}:
        attrs = event.get('data', {}).get('attributes', {})
        reason = ''
        if isinstance(attrs, dict):
            reason = str(attrs.get('rejection_reason') or attrs.get('reason') or '')
        _mark_kyb_rejected(kyb, reason=reason)
    elif event_type in {'merchant.pending', 'merchant.submitted'}:
        _mark_kyb_pending(kyb)
    else:
        logger.info('Unhandled PayMongo merchant event type: %s', event_type)

    return True
