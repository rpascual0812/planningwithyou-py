"""Confirm quotation payments when the customer returns from checkout."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from subscriptions.xendit_client import XenditError, retrieve_session

from .models import QuotationPaymentLink
from .payment_links import serialize_public_payment_link
from .paymongo_webhook import (
    _PAYMONGO_LINK_PAID_STATUSES,
    _extract_payment_from_checkout_session,
    _payment_breakdown_for_link,
    _record_booking_payment,
)
from .xendit_booking_webhook import apply_xendit_booking_payment_session_completed

logger = logging.getLogger(__name__)

_LINK_SELECT_RELATED = (
    'quotation',
    'quotation__contact',
    'quotation__created_by',
    'quotation__company',
    'company',
    'company__kyb_verification',
)


def _link_queryset():
    return QuotationPaymentLink.objects.select_related(*_LINK_SELECT_RELATED)


def _xendit_sub_account_id(link: QuotationPaymentLink) -> str:
    company = getattr(link, 'company', None)
    kyb = getattr(company, 'kyb_verification', None) if company is not None else None
    return (getattr(kyb, 'xendit_account_id', None) or '').strip()


def _paymongo_metadata(link: QuotationPaymentLink) -> dict[str, str]:
    return {
        'booking_payment_link_id': str(link.pk),
        'quotation_id': str(link.quotation_id),
        'account_id': str(link.account_id),
        'company_id': str(link.company_id),
        'payment_provider': link.payment_provider,
    }


def _sync_xendit_link(link: QuotationPaymentLink) -> bool:
    session_id = (link.xendit_payment_session_id or '').strip()
    if not session_id:
        logger.info('Xendit confirm skipped: link #%s has no session id.', link.pk)
        return False
    try:
        session = retrieve_session(
            session_id,
            for_user_id=_xendit_sub_account_id(link) or None,
        )
    except XenditError:
        logger.warning('Xendit session %s could not be retrieved for link #%s.', session_id, link.pk)
        return False
    return apply_xendit_booking_payment_session_completed(session)


def _sync_paymongo_link(link: QuotationPaymentLink) -> bool:
    session_id = (link.paymongo_checkout_session_id or '').strip()
    if not session_id:
        logger.info('PayMongo confirm skipped: link #%s has no checkout session id.', link.pk)
        return False
    metadata = _paymongo_metadata(link)
    payment_info = _extract_payment_from_checkout_session(
        session_id,
        metadata=metadata,
        event_type='checkout.session.completed',
    )
    if payment_info is None:
        return False

    status = (payment_info.get('status') or '').strip().lower()
    if status not in _PAYMONGO_LINK_PAID_STATUSES:
        return False

    payment_attrs = payment_info.get('payment_attrs')
    if not isinstance(payment_attrs, dict):
        payment_attrs = {}
    breakdown = _payment_breakdown_for_link(link, payment_attrs)
    api_response = {
        'source': 'public_payment_link_confirm',
        'payment': payment_info.get('resource'),
        'session': payment_info.get('session_resource'),
    }
    _record_booking_payment(
        link,
        transaction_id=payment_info['payment_id'],
        transaction_status=payment_info['status'],
        payment_method=payment_info['payment_method'],
        breakdown=breakdown,
        api_response=api_response,
    )
    return True


def _mark_success_return_confirmed(link: QuotationPaymentLink) -> None:
    if link.success_return_confirmed_at is not None:
        return
    link.success_return_confirmed_at = timezone.now()
    link.save(update_fields=['success_return_confirmed_at', 'updated_at'])


@transaction.atomic
def confirm_quotation_payment_link(link: QuotationPaymentLink) -> dict:
    """
    Verify checkout status with the provider and record payment when paid.

    The success return URL may only be consumed once per link; repeat calls
    return ``already_recorded`` without contacting the payment provider again.
    """
    link.refresh_from_db()
    if link.success_return_confirmed_at is not None:
        return {
            'confirmed': link.status == QuotationPaymentLink.Status.PAID,
            'pending': False,
            'already_recorded': True,
            'payment_link': serialize_public_payment_link(link),
        }

    if link.status == QuotationPaymentLink.Status.PAID:
        _mark_success_return_confirmed(link)
        link.refresh_from_db()
        return {
            'confirmed': True,
            'pending': False,
            'already_recorded': False,
            'payment_link': serialize_public_payment_link(link),
        }

    if (
        link.status == QuotationPaymentLink.Status.PENDING
        and link.expires_at < timezone.now()
    ):
        link.status = QuotationPaymentLink.Status.EXPIRED
        link.save(update_fields=['status', 'updated_at'])
        return {
            'confirmed': False,
            'pending': False,
            'already_recorded': False,
            'payment_link': serialize_public_payment_link(link),
        }

    recorded = False
    if link.payment_provider == QuotationPaymentLink.PaymentProvider.XENDIT:
        recorded = _sync_xendit_link(link)
    else:
        recorded = _sync_paymongo_link(link)

    link.refresh_from_db()
    confirmed = link.status == QuotationPaymentLink.Status.PAID
    if confirmed:
        _mark_success_return_confirmed(link)
        link.refresh_from_db()
    return {
        'confirmed': confirmed,
        'pending': not confirmed and not recorded,
        'already_recorded': False,
        'payment_link': serialize_public_payment_link(link),
    }


def confirm_quotation_payment_link_by_token(token: str) -> tuple[QuotationPaymentLink | None, dict]:
    link = _link_queryset().filter(public_token=token).first()
    if link is None:
        return None, {}
    return link, confirm_quotation_payment_link(link)
