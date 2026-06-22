"""Apply Xendit payment session webhooks to quotation payment links."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from subscriptions.xendit_client import retrieve_session, xendit_session_id

from .models import QuotationPaymentLink
from .paymongo_webhook import _record_booking_payment

logger = logging.getLogger(__name__)

_BOOKING_LINK_KIND = 'quotation_payment_link'
_QUOTE_LINK_REFERENCE_PREFIX = 'quote-link-'
_LINK_SELECT_RELATED = (
    'quotation',
    'quotation__contact',
    'quotation__created_by',
    'company',
)


def _metadata_from_session(session: dict) -> dict[str, str]:
    metadata = session.get('metadata')
    if not isinstance(metadata, dict):
        return {}
    return {str(k): str(v) for k, v in metadata.items()}


def _session_completed(session: dict) -> bool:
    return str(session.get('status') or '').strip().upper() == 'COMPLETED'


def _link_queryset():
    return QuotationPaymentLink.objects.select_related(*_LINK_SELECT_RELATED)


def _link_by_session_id(session_id: str) -> QuotationPaymentLink | None:
    session_id = (session_id or '').strip()
    if not session_id:
        return None
    return _link_queryset().filter(xendit_payment_session_id=session_id).order_by('-id').first()


def _resolve_link(metadata: dict[str, str], session: dict) -> QuotationPaymentLink | None:
    link_id = (metadata.get('booking_payment_link_id') or '').strip()
    if link_id.isdigit():
        link = _link_queryset().filter(pk=int(link_id)).first()
        if link is not None:
            return link

    session_id = xendit_session_id(session)
    link = _link_by_session_id(session_id)
    if link is not None:
        return link

    reference = str(session.get('reference_id') or '').strip()
    if reference.startswith(_QUOTE_LINK_REFERENCE_PREFIX):
        token = reference.removeprefix(_QUOTE_LINK_REFERENCE_PREFIX).strip()
        if token:
            return _link_queryset().filter(public_token=token).first()
    return None


def _enrich_session(session: dict) -> dict:
    """
    Webhook payloads often omit metadata. Fetch the full session when we cannot
    already identify the quotation payment link from the webhook body alone.
    """
    session_id = xendit_session_id(session)
    if not session_id:
        return session

    metadata = _metadata_from_session(session)
    if (metadata.get('kind') or '').strip() == _BOOKING_LINK_KIND:
        return session
    if (metadata.get('booking_payment_link_id') or '').strip().isdigit():
        return session

    reference = str(session.get('reference_id') or '').strip()
    if reference.startswith(_QUOTE_LINK_REFERENCE_PREFIX):
        return session

    link = _link_by_session_id(session_id)
    if link is not None:
        return session

    try:
        full = retrieve_session(session_id)
    except Exception:
        logger.warning(
            'Xendit session %s could not be retrieved for booking payment.',
            session_id,
        )
        return session
    if not isinstance(full, dict):
        return session

    merged = dict(full)
    merged.update(session)
    if not xendit_session_id(merged):
        merged['payment_session_id'] = session_id
    return merged


def _record_xendit_booking_payment(link: QuotationPaymentLink, session: dict) -> None:
    payment_id = str(session.get('payment_id') or xendit_session_id(session) or '').strip()
    breakdown = {
        'charge_amount': link.charge_amount,
        'base_amount': link.base_amount,
        'platform_fee': link.platform_fee,
        'processing_fee': link.processing_fee_estimate,
        'net_amount': max(
            link.charge_amount - link.platform_fee - link.processing_fee_estimate,
            Decimal('0'),
        ),
    }
    _record_booking_payment(
        link,
        transaction_id=payment_id,
        transaction_status='paid',
        payment_method='xendit',
        breakdown=breakdown,
        api_response=session,
    )


@transaction.atomic
def apply_xendit_booking_payment_session_completed(session: dict) -> bool:
    if not _session_completed(session):
        return False

    session = _enrich_session(session)
    link = _resolve_link(_metadata_from_session(session), session)
    if link is None:
        return False

    _record_xendit_booking_payment(link, session)
    logger.info(
        'Recorded Xendit quotation payment for link #%s (quotation #%s).',
        link.pk,
        link.quotation_id,
    )
    return True


@transaction.atomic
def apply_xendit_booking_payment_session_failed(session: dict) -> bool:
    session = _enrich_session(session)
    link = _resolve_link(_metadata_from_session(session), session)
    if link is None:
        return False
    if link.status == QuotationPaymentLink.Status.PENDING:
        link.save(update_fields=['updated_at'])
    return True
