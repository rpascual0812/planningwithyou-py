"""Verify PayMongo webhooks and apply payment outcomes."""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import BookingPayment, BookingPaymentLink
from .paymongo_client import PayMongoError, retrieve_checkout_session, retrieve_payment

# PayMongo payment ``attributes.status`` values that mark the link as collected.
_PAYMONGO_LINK_PAID_STATUSES = frozenset({'paid', 'succeeded'})


def verify_paymongo_signature(payload: bytes, signature_header: str | None) -> bool:
    secret = (getattr(settings, 'PAYMONGO_WEBHOOK_SECRET', None) or '').strip()
    if not secret or not signature_header:
        return False
    parts: dict[str, str] = {}
    for piece in signature_header.split(','):
        if '=' in piece:
            key, value = piece.split('=', 1)
            parts[key.strip()] = value.strip()
    timestamp = parts.get('t')
    signature = parts.get('te') or parts.get('v1') or parts.get('li')
    if not timestamp or not signature:
        return False
    signed_payload = f'{timestamp}.{payload.decode("utf-8")}'.encode('utf-8')
    expected = hmac.new(
        secret.encode('utf-8'),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _payment_link_from_metadata(metadata: dict) -> BookingPaymentLink | None:
    link_id = metadata.get('booking_payment_link_id')
    if not link_id:
        return None
    try:
        pk = int(link_id)
    except (TypeError, ValueError):
        return None
    return (
        BookingPaymentLink.objects.select_related('booking', 'company')
        .filter(pk=pk)
        .first()
    )


def _resolve_payment_link(
    metadata: dict,
    checkout_session_id: str = '',
) -> BookingPaymentLink | None:
    link = _payment_link_from_metadata(metadata)
    if link is not None:
        return link
    session_id = (checkout_session_id or '').strip()
    if not session_id:
        return None
    return (
        BookingPaymentLink.objects.select_related('booking', 'company')
        .filter(paymongo_checkout_session_id=session_id)
        .first()
    )


def _amount_php_from_paymongo_attributes(
    attrs: dict,
    field: str = 'amount',
) -> Decimal | None:
    """Convert a PayMongo centavo field on payment attributes to PHP decimal."""
    raw = attrs.get(field)
    if raw is None or raw == '':
        return None
    try:
        return (Decimal(str(raw)) / Decimal('100')).quantize(Decimal('0.01'))
    except Exception:
        return None


def _payment_breakdown_for_link(
    link: BookingPaymentLink,
    payment_attrs: dict,
) -> dict[str, Decimal]:
    """
    Build stored breakdown: quote/base and platform fee from the link; gross,
    processing fee, and net from PayMongo when present.
    """
    charge = _amount_php_from_paymongo_attributes(payment_attrs, 'amount')
    processing = _amount_php_from_paymongo_attributes(payment_attrs, 'fee')
    net = _amount_php_from_paymongo_attributes(payment_attrs, 'net_amount')

    if charge is None:
        charge = link.charge_amount or Decimal('0')
    if processing is None:
        processing = link.processing_fee_estimate or Decimal('0')
    if net is None and charge is not None and processing is not None:
        net = (charge - processing).quantize(Decimal('0.01'))
    if net is None:
        net = Decimal('0')

    base = link.base_amount or Decimal('0')
    platform = link.platform_fee or Decimal('0')

    return {
        'charge_amount': charge,
        'base_amount': base,
        'platform_fee': platform,
        'processing_fee': processing,
        'net_amount': net,
    }


def _payment_method_from_attributes(attrs: dict, resource_type: str = '') -> str:
    source = attrs.get('source')
    source_type = source.get('type') if isinstance(source, dict) else ''
    return (
        (attrs.get('payment_method_type') or source_type or resource_type or 'paymongo')
    ).strip() or 'paymongo'


def _payment_id_from_resource(resource: dict) -> str:
    return str(resource.get('id') or '').strip()


def _payment_status_from_attributes(attrs: dict, *, fallback: str = '') -> str:
    status = (attrs.get('status') or fallback or '').strip()
    return status or 'unknown'


def _extract_payment_from_event(event: dict) -> dict | None:
    """
    Parse PayMongo payment id and status from a webhook event.

    Returns dict with keys: payment_id, status, amount, payment_method, metadata,
    checkout_session_id, resource (raw payment data object).
    """
    data = event.get('data')
    if not isinstance(data, dict):
        return None
    event_attrs = data.get('attributes')
    if not isinstance(event_attrs, dict):
        return None

    event_type = (event.get('type') or event_attrs.get('type') or '').strip()
    resource = event_attrs.get('data')
    if not isinstance(resource, dict):
        return None

    resource_type = (resource.get('type') or '').strip()
    resource_attrs = resource.get('attributes')
    if not isinstance(resource_attrs, dict):
        resource_attrs = {}

    metadata = resource_attrs.get('metadata') or {}
    if not isinstance(metadata, dict):
        metadata = {}
    if not metadata and isinstance(event_attrs.get('metadata'), dict):
        metadata = event_attrs['metadata']

    checkout_session_id = (resource_attrs.get('checkout_session_id') or '').strip()

    if resource_type == 'payment':
        payment_id = _payment_id_from_resource(resource)
        if not payment_id:
            return None
        return {
            'payment_id': payment_id,
            'status': _payment_status_from_attributes(resource_attrs),
            'payment_attrs': resource_attrs,
            'payment_method': _payment_method_from_attributes(resource_attrs, 'payment'),
            'metadata': metadata,
            'checkout_session_id': checkout_session_id,
            'event_type': event_type,
            'resource': resource,
        }

    if resource_type == 'checkout_session' and event_type == 'checkout.session.completed':
        session_id = _payment_id_from_resource(resource)
        return _extract_payment_from_checkout_session(
            session_id,
            metadata=metadata,
            event_type=event_type,
            session_resource=resource,
        )

    return None


def _extract_payment_from_checkout_session(
    session_id: str,
    *,
    metadata: dict,
    event_type: str = '',
    session_resource: dict | None = None,
) -> dict | None:
    """Resolve payment id/status via checkout session (PayMongo API)."""
    if not session_id:
        return None
    try:
        session = retrieve_checkout_session(session_id)
    except PayMongoError:
        return None

    session_attrs = session.get('attributes')
    if not isinstance(session_attrs, dict):
        session_attrs = {}

    if not metadata and isinstance(session_attrs.get('metadata'), dict):
        metadata = session_attrs['metadata']

    payment_ids: list[str] = []
    payments = session_attrs.get('payments')
    if isinstance(payments, list):
        for entry in payments:
            if isinstance(entry, dict):
                pid = _payment_id_from_resource(entry)
            else:
                pid = str(entry or '').strip()
            if pid:
                payment_ids.append(pid)

    payment_id = payment_ids[-1] if payment_ids else ''
    if not payment_id:
        return None

    try:
        payment = retrieve_payment(payment_id)
    except PayMongoError:
        return None

    payment_attrs = payment.get('attributes')
    if not isinstance(payment_attrs, dict):
        payment_attrs = {}

    return {
        'payment_id': payment_id,
        'status': _payment_status_from_attributes(payment_attrs),
        'payment_attrs': payment_attrs,
        'payment_method': _payment_method_from_attributes(payment_attrs, 'payment'),
        'metadata': metadata,
        'checkout_session_id': session_id,
        'event_type': event_type,
        'resource': payment,
        'session_resource': session_resource or session,
    }


@transaction.atomic
def _record_booking_payment(
    link: BookingPaymentLink,
    *,
    transaction_id: str,
    transaction_status: str,
    payment_method: str,
    breakdown: dict[str, Decimal],
    api_response: dict,
) -> BookingPayment:
    """Persist PayMongo payment details on ``booking_payments`` (upsert by payment id)."""
    payment_id = (transaction_id or '').strip()
    status = (transaction_status or 'unknown').strip()
    now = timezone.now()

    charge_amount = breakdown['charge_amount']
    base_amount = breakdown['base_amount']
    platform_fee = breakdown['platform_fee']
    processing_fee = breakdown['processing_fee']
    net_amount = breakdown['net_amount']

    notes = f'PayMongo payment {payment_id or "—"} (link #{link.pk})'

    breakdown_fields = [
        'transaction_status',
        'payment_method',
        'amount',
        'charge_amount',
        'base_amount',
        'platform_fee',
        'processing_fee',
        'net_amount',
        'api_response',
        'transaction_date',
        'notes',
        'updated_at',
    ]

    existing = None
    if payment_id:
        existing = (
            BookingPayment.objects.filter(
                booking_id=link.booking_id,
                transaction_id=payment_id,
                deleted_at__isnull=True,
            )
            .order_by('-id')
            .first()
        )

    if existing is not None:
        existing.transaction_status = status
        existing.payment_method = payment_method or existing.payment_method
        existing.amount = base_amount
        existing.charge_amount = charge_amount
        existing.base_amount = base_amount
        existing.platform_fee = platform_fee
        existing.processing_fee = processing_fee
        existing.net_amount = net_amount
        existing.api_response = api_response
        existing.transaction_date = now
        existing.notes = notes
        existing.save(update_fields=breakdown_fields)
        payment = existing
    else:
        payment = BookingPayment.objects.create(
            booking_id=link.booking_id,
            account_id=link.account_id,
            company_id=link.company_id,
            payment_method=payment_method or 'paymongo',
            amount=base_amount,
            charge_amount=charge_amount,
            base_amount=base_amount,
            platform_fee=platform_fee,
            processing_fee=processing_fee,
            net_amount=net_amount,
            tax=Decimal('0'),
            transaction_id=payment_id,
            transaction_status=status,
            notes=notes,
            api_response=api_response,
            transaction_date=now,
        )

    status_lower = status.lower()
    if status_lower in _PAYMONGO_LINK_PAID_STATUSES:
        if link.status != BookingPaymentLink.Status.PAID:
            link.status = BookingPaymentLink.Status.PAID
            link.paid_at = now
            link.save(update_fields=['status', 'paid_at', 'updated_at'])
    elif status_lower in {'failed', 'cancelled', 'canceled'}:
        if link.status == BookingPaymentLink.Status.PENDING:
            link.save(update_fields=['updated_at'])

    return payment


def normalize_paymongo_webhook_body(body: dict) -> list[dict]:
    """Flatten PayMongo webhook JSON into handler-friendly event dicts."""
    events: list[dict] = []
    root_data = body.get('data')
    if not isinstance(root_data, dict):
        if body.get('type'):
            events.append(body)
        return events

    attrs = root_data.get('attributes')
    if not isinstance(attrs, dict):
        return events

    event_type = (attrs.get('type') or root_data.get('type') or body.get('type') or '').strip()
    nested = attrs.get('data')
    metadata: dict = {}
    checkout_session_id = ''

    if isinstance(nested, dict):
        nested_attrs = nested.get('attributes')
        if isinstance(nested_attrs, dict):
            metadata = nested_attrs.get('metadata') or {}
            if not isinstance(metadata, dict):
                metadata = {}
            checkout_session_id = (nested_attrs.get('checkout_session_id') or '').strip()
        elif isinstance(attrs.get('metadata'), dict):
            metadata = attrs['metadata']

    events.append(
        {
            'type': event_type,
            'data': {
                'id': nested.get('id') if isinstance(nested, dict) else root_data.get('id'),
                'attributes': {
                    'type': event_type,
                    'metadata': metadata,
                    'checkout_session_id': checkout_session_id,
                    'data': nested,
                },
            },
        },
    )
    return events


@transaction.atomic
def handle_paymongo_webhook_event(event: dict) -> bool:
    """
    Process a PayMongo webhook event. Always records ``booking_payments`` when a
    payment id and status are present, regardless of outcome.
    """
    payment_info = _extract_payment_from_event(event)
    if payment_info is None:
        return False

    link = _resolve_payment_link(
        payment_info.get('metadata') or {},
        payment_info.get('checkout_session_id') or '',
    )
    if link is None:
        return False

    if (
        link.expires_at
        and link.expires_at < timezone.now()
        and link.status == BookingPaymentLink.Status.PENDING
        and payment_info['status'].lower() not in _PAYMONGO_LINK_PAID_STATUSES
    ):
        link.status = BookingPaymentLink.Status.EXPIRED
        link.save(update_fields=['status', 'updated_at'])

    api_response = {
        'event': event,
        'payment': payment_info.get('resource'),
        'session': payment_info.get('session_resource'),
    }

    payment_attrs = payment_info.get('payment_attrs')
    if not isinstance(payment_attrs, dict):
        payment_attrs = {}
    breakdown = _payment_breakdown_for_link(link, payment_attrs)

    _record_booking_payment(
        link,
        transaction_id=payment_info['payment_id'],
        transaction_status=payment_info['status'],
        payment_method=payment_info['payment_method'],
        breakdown=breakdown,
        api_response=api_response,
    )
    return True


def parse_webhook_body(raw: bytes) -> dict:
    return json.loads(raw.decode('utf-8'))
