"""Create and expose public booking payment links."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from companies.kyb import live_payments_allowed
from companies.models import Company

from .models import BookingItem, BookingPaymentLink
from .payment_pricing import PaymentLinkPricing, amount_to_centavos, compute_payment_link_pricing
from .payment_summary import booking_is_fully_paid, booking_remaining_balance
from .paymongo_client import PayMongoError, create_checkout_session, paymongo_configured


class PaymentLinkError(Exception):
    pass


def _company_can_accept_payments(company: Company) -> bool:
    kyb = getattr(company, 'kyb_verification', None)
    return live_payments_allowed(kyb)


def public_payment_url(token: uuid.UUID | str) -> str:
    base = (getattr(settings, 'FRONTEND_URL', None) or '').rstrip('/')
    return f'{base}/pay/{token}'


def create_booking_payment_link(
    booking: BookingItem,
    *,
    charge_base_amount=None,
    created_by=None,
    expires_in_days: int = 14,
) -> BookingPaymentLink:
    if not paymongo_configured(booking.company_id):
        raise PaymentLinkError('PayMongo is not configured on the server.')

    company = Company.all_objects.select_related('kyb_verification').filter(
        pk=booking.company_id,
    ).first()
    if company is None:
        raise PaymentLinkError('Company not found.')
    if not _company_can_accept_payments(company):
        raise PaymentLinkError(
            'Live payments are not enabled. Complete KYB verification first.',
        )

    if booking_is_fully_paid(booking):
        raise PaymentLinkError('This booking is already fully paid.')

    remaining = booking_remaining_balance(booking)
    if charge_base_amount is None:
        base_amount = booking.required_downpayment_amount or Decimal('0')
        if base_amount <= Decimal('0'):
            base_amount = remaining
    else:
        base_amount = Decimal(str(charge_base_amount))

    if base_amount <= Decimal('0'):
        raise PaymentLinkError('Payment amount must be greater than zero.')
    if base_amount > remaining:
        raise PaymentLinkError(
            f'Payment amount cannot exceed the remaining balance ({remaining}).',
        )

    try:
        pricing = compute_payment_link_pricing(base_amount)
    except ValueError as exc:
        raise PaymentLinkError(str(exc)) from exc

    token = uuid.uuid4()
    expires_at = timezone.now() + timedelta(days=expires_in_days)
    public_url = public_payment_url(token)
    success_url = f'{public_url}?status=success'
    cancel_url = f'{public_url}?status=cancelled'

    link = BookingPaymentLink(
        booking=booking,
        account_id=booking.account_id,
        company_id=booking.company_id,
        public_token=token,
        base_amount=pricing.base_amount,
        platform_fee=pricing.platform_fee,
        processing_fee_estimate=pricing.processing_fee_estimate,
        charge_amount=pricing.charge_amount,
        currency='PHP',
        status=BookingPaymentLink.Status.PENDING,
        expires_at=expires_at,
        created_by=created_by,
    )

    line_items = [
        {
            'amount': amount_to_centavos(pricing.charge_amount),
            'currency': 'PHP',
            'name': f'Booking {booking.unique_id or booking.title}',
            'quantity': 1,
            'description': (
                f'Quote {pricing.base_amount} PHP + fees '
                f'(booking {booking.unique_id or booking.pk})'
            )[:255],
        },
    ]
    metadata = {
        'booking_payment_link_id': '',  # filled after save
        'booking_id': str(booking.pk),
        'account_id': str(booking.account_id),
        'company_id': str(booking.company_id),
    }

    try:
        BookingPaymentLink.objects.filter(
            booking_id=booking.pk,
            status=BookingPaymentLink.Status.PENDING,
        ).update(status=BookingPaymentLink.Status.CANCELLED)

        link.save()
        metadata['booking_payment_link_id'] = str(link.pk)
        session = create_checkout_session(
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            description=f'Payment for booking {booking.unique_id or booking.title}',
            reference_number=str(booking.unique_id or booking.pk),
            metadata=metadata,
            company_id=booking.company_id,
        )
    except PayMongoError as exc:
        link.delete()
        raise PaymentLinkError(str(exc)) from exc

    attrs = session.get('attributes') or {}
    link.paymongo_checkout_session_id = session.get('id') or ''
    checkout_url = attrs.get('checkout_url') or ''
    if not checkout_url and isinstance(attrs.get('redirect'), dict):
        checkout_url = attrs['redirect'].get('checkout_url') or attrs['redirect'].get('url') or ''
    link.paymongo_checkout_url = checkout_url
    if not link.paymongo_checkout_url:
        link.delete()
        raise PaymentLinkError('PayMongo did not return a checkout URL.')
    link.save(
        update_fields=[
            'paymongo_checkout_session_id',
            'paymongo_checkout_url',
            'updated_at',
        ],
    )
    return link


def serialize_public_payment_link(link: BookingPaymentLink) -> dict:
    booking = link.booking
    company = link.company
    currency_symbol = '₱'
    currency_code = link.currency or 'PHP'
    account = getattr(booking, 'account', None)
    country = getattr(account, 'country', None) if account else None
    if country is not None:
        currency_symbol = (country.currency_symbol or '').strip() or currency_symbol
        currency_code = (country.currency_code or '').strip() or currency_code
    pricing = PaymentLinkPricing(
        base_amount=link.base_amount,
        platform_fee=link.platform_fee,
        processing_fee_estimate=link.processing_fee_estimate,
        charge_amount=link.charge_amount,
    )
    expired = link.expires_at < timezone.now() and link.status == BookingPaymentLink.Status.PENDING
    return {
        'token': str(link.public_token),
        'status': BookingPaymentLink.Status.EXPIRED if expired else link.status,
        'booking_title': booking.title,
        'booking_unique_id': booking.unique_id,
        'company_name': company.name if company else '',
        'currency': currency_code,
        'currency_symbol': currency_symbol,
        'base_amount': str(link.base_amount),
        'platform_fee': str(link.platform_fee),
        'processing_fee_estimate': str(link.processing_fee_estimate),
        'charge_amount': str(link.charge_amount),
        'fees_total': str(pricing.fees_total),
        'checkout_url': link.paymongo_checkout_url if link.status == BookingPaymentLink.Status.PENDING and not expired else '',
        'public_url': public_payment_url(link.public_token),
        'expires_at': link.expires_at.isoformat(),
        'paid_at': link.paid_at.isoformat() if link.paid_at else None,
    }
