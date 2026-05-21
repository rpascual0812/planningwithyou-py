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
from .payment_validity import booking_has_valid_payment


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


def _mark_link_paid(
    link: BookingPaymentLink,
    *,
    transaction_id: str,
    payment_method: str,
    api_response: dict,
) -> BookingPayment | None:
    if link.status == BookingPaymentLink.Status.PAID:
        return (
            BookingPayment.objects.filter(
                booking_id=link.booking_id,
                deleted_at__isnull=True,
                transaction_status__iexact='paid',
            )
            .order_by('-id')
            .first()
        )

    now = timezone.now()
    link.status = BookingPaymentLink.Status.PAID
    link.paid_at = now
    link.save(update_fields=['status', 'paid_at', 'updated_at'])

    payment = BookingPayment.objects.create(
        booking_id=link.booking_id,
        account_id=link.account_id,
        company_id=link.company_id,
        payment_method=payment_method or 'paymongo',
        amount=link.charge_amount,
        tax=Decimal('0'),
        transaction_id=transaction_id,
        transaction_status='paid',
        notes=f'PayMongo checkout link #{link.pk}',
        api_response=api_response,
        transaction_date=now,
    )
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
    transaction_id = ''
    payment_method = ''
    checkout_session_id = ''

    if isinstance(nested, dict):
        nested_attrs = nested.get('attributes')
        if isinstance(nested_attrs, dict):
            metadata = nested_attrs.get('metadata') or {}
            if not isinstance(metadata, dict):
                metadata = {}
            source = nested_attrs.get('source')
            source_type = source.get('type') if isinstance(source, dict) else ''
            payment_method = (
                nested_attrs.get('payment_method_type')
                or source_type
                or nested.get('type')
                or ''
            )
            checkout_session_id = nested_attrs.get('checkout_session_id') or ''
        transaction_id = nested.get('id') or ''

    if not metadata and isinstance(attrs.get('metadata'), dict):
        metadata = attrs['metadata']

    events.append(
        {
            'type': event_type,
            'data': {
                'id': transaction_id or root_data.get('id'),
                'attributes': {
                    'metadata': metadata,
                    'payment_method_type': payment_method,
                    'checkout_session_id': checkout_session_id,
                },
            },
        },
    )
    return events


@transaction.atomic
def handle_paymongo_webhook_event(event: dict) -> bool:
    """
    Process a PayMongo webhook event dict. Returns True when handled.
    """
    data = event.get('data')
    if not isinstance(data, dict):
        return False
    attributes = data.get('attributes')
    if not isinstance(attributes, dict):
        return False

    event_type = (event.get('type') or attributes.get('type') or '').strip()
    metadata = attributes.get('metadata') or {}
    if not isinstance(metadata, dict):
        metadata = {}

    link = _payment_link_from_metadata(metadata)
    if link is None and attributes.get('checkout_session_id'):
        link = (
            BookingPaymentLink.objects.select_related('booking')
            .filter(paymongo_checkout_session_id=attributes.get('checkout_session_id'))
            .first()
        )
    if link is None:
        return False

    paid_types = {
        'checkout.session.completed',
        'payment.paid',
        'payment.succeeded',
    }
    if event_type not in paid_types:
        return False

    if link.status == BookingPaymentLink.Status.PAID:
        return True

    if link.expires_at and link.expires_at < timezone.now():
        link.status = BookingPaymentLink.Status.EXPIRED
        link.save(update_fields=['status', 'updated_at'])
        return False

    transaction_id = (
        attributes.get('payment_id')
        or attributes.get('payment_intent_id')
        or data.get('id')
        or ''
    )
    payment_method = attributes.get('payment_method_type') or attributes.get('type') or 'paymongo'
    _mark_link_paid(
        link,
        transaction_id=str(transaction_id),
        payment_method=str(payment_method),
        api_response=event,
    )
    return True


def parse_webhook_body(raw: bytes) -> dict:
    return json.loads(raw.decode('utf-8'))
