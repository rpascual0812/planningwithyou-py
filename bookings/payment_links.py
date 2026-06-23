"""Create and expose public booking payment links."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from companies.models import Company

from .models import Quotation, QuotationPaymentLink
from .payment_pricing import PaymentLinkPricing, amount_to_centavos, compute_payment_link_pricing
from .payment_providers import (
    PROVIDER_LABELS,
    PROVIDER_PAYMONGO,
    PROVIDER_XENDIT,
    assert_payment_provider_link_ready,
    normalize_payment_provider,
    verified_payment_providers,
)
from .payment_summary import booking_is_fully_paid, booking_remaining_balance
from .quotation_pricing_adjustments import sync_quotation_total_amount
from .xendit_payment_links import create_quotation_payment_session
from payments.paymongo_config import company_can_accept_paymongo_payments, get_paymongo_company_context

from payments.paymongo_platform_client import (
    PayMongoError,
    create_checkout_session_for_company,
)

from .paymongo_client import paymongo_configured
from subscriptions.xendit_client import XenditError, payment_link_url, xendit_configured, xendit_session_id


class PaymentLinkError(Exception):
    pass


def public_payment_url(token: uuid.UUID | str) -> str:
    base = (getattr(settings, 'FRONTEND_URL', None) or '').rstrip('/')
    return f'{base}/pay/{token}'


def xendit_https_frontend_base() -> str:
    explicit = getattr(settings, 'XENDIT_RETURN_URL_BASE', None) or ''
    base = (explicit or getattr(settings, 'FRONTEND_URL', None) or '').rstrip('/')
    if not base.startswith('https://'):
        raise PaymentLinkError(
            'Xendit requires HTTPS return URLs. Set XENDIT_RETURN_URL_BASE to your '
            'public https frontend URL (for example an ngrok tunnel), or set '
            'FRONTEND_URL to an https:// URL.',
        )
    return base


def xendit_payment_return_urls(token: uuid.UUID | str) -> tuple[str, str, str]:
    """HTTPS success URL, cancel URL, and public pay page URL for Xendit sessions."""
    public_url = f'{xendit_https_frontend_base()}/pay/{token}'
    return (
        f'{public_url}?status=success',
        f'{public_url}?status=cancelled',
        public_url,
    )


def _load_company(booking: Quotation) -> Company:
    company = Company.all_objects.select_related('kyb_verification').filter(
        pk=booking.company_id,
    ).first()
    if company is None:
        raise PaymentLinkError('Company not found.')
    return company


def _resolve_base_amount(booking: Quotation, charge_base_amount) -> Decimal:
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
    return base_amount


def _create_paymongo_link(
    booking: Quotation,
    *,
    company: Company,
    pricing: PaymentLinkPricing,
    token: uuid.UUID,
    expires_at,
    public_url: str,
    success_url: str,
    cancel_url: str,
    created_by,
) -> QuotationPaymentLink:
    if not paymongo_configured(booking.company_id):
        raise PaymentLinkError('PayMongo is not configured on the server.')
    if not company_can_accept_paymongo_payments(booking.company_id):
        raise PaymentLinkError(
            'PayMongo is not connected for this company. Complete PayMongo verification first.',
        )
    paymongo_ctx = get_paymongo_company_context(booking.company_id)
    if paymongo_ctx is None:
        raise PaymentLinkError('PayMongo child account is not ready for payments.')

    link = QuotationPaymentLink(
        quotation=booking,
        account_id=booking.account_id,
        company_id=booking.company_id,
        public_token=token,
        payment_provider=QuotationPaymentLink.PaymentProvider.PAYMONGO,
        base_amount=pricing.base_amount,
        platform_fee=pricing.platform_fee,
        processing_fee_estimate=pricing.processing_fee_estimate,
        charge_amount=pricing.charge_amount,
        currency='PHP',
        status=QuotationPaymentLink.Status.PENDING,
        expires_at=expires_at,
        created_by=created_by,
    )

    line_items = [
        {
            'amount': amount_to_centavos(pricing.charge_amount),
            'currency': 'PHP',
            'name': f'Quotation {booking.unique_id or booking.title}',
            'quantity': 1,
            'description': (
                f'Quote {pricing.base_amount} PHP + fees '
                f'(booking {booking.unique_id or booking.pk})'
            )[:255],
        },
    ]
    metadata = {
        'booking_payment_link_id': '',
        'quotation_id': str(booking.pk),
        'account_id': str(booking.account_id),
        'company_id': str(booking.company_id),
        'payment_provider': PROVIDER_PAYMONGO,
    }

    try:
        QuotationPaymentLink.objects.filter(
            quotation_id=booking.pk,
            status=QuotationPaymentLink.Status.PENDING,
        ).update(status=QuotationPaymentLink.Status.CANCELLED)

        link.save()
        metadata['booking_payment_link_id'] = str(link.pk)
        session = create_checkout_session_for_company(
            child_account_id=paymongo_ctx.child_account_id,
            platform_merchant_id=paymongo_ctx.platform_merchant_id,
            platform_fee_bps=paymongo_ctx.platform_fee_bps,
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            description=f'Payment for booking {booking.unique_id or booking.title}',
            reference_number=str(booking.unique_id or booking.pk),
            metadata=metadata,
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


def _create_xendit_link(
    booking: Quotation,
    *,
    company: Company,
    pricing: PaymentLinkPricing,
    token: uuid.UUID,
    expires_at,
    public_url: str,
    success_url: str,
    cancel_url: str,
    created_by,
) -> QuotationPaymentLink:
    if not xendit_configured():
        raise PaymentLinkError('Xendit is not configured on the server.')
    kyb = getattr(company, 'kyb_verification', None)
    sub_account_id = (getattr(kyb, 'xendit_account_id', None) or '').strip()
    if not sub_account_id:
        raise PaymentLinkError(
            'Xendit is not connected for this company. Complete Xendit verification first.',
        )

    link = QuotationPaymentLink(
        quotation=booking,
        account_id=booking.account_id,
        company_id=booking.company_id,
        public_token=token,
        payment_provider=QuotationPaymentLink.PaymentProvider.XENDIT,
        base_amount=pricing.base_amount,
        platform_fee=pricing.platform_fee,
        processing_fee_estimate=pricing.processing_fee_estimate,
        charge_amount=pricing.charge_amount,
        currency='PHP',
        status=QuotationPaymentLink.Status.PENDING,
        expires_at=expires_at,
        created_by=created_by,
    )

    metadata = {
        'booking_payment_link_id': '',
        'quotation_id': str(booking.pk),
        'account_id': str(booking.account_id),
        'company_id': str(booking.company_id),
        'payment_provider': PROVIDER_XENDIT,
        'kind': 'quotation_payment_link',
    }
    reference_id = f'quote-link-{token}'

    try:
        QuotationPaymentLink.objects.filter(
            quotation_id=booking.pk,
            status=QuotationPaymentLink.Status.PENDING,
        ).update(status=QuotationPaymentLink.Status.CANCELLED)

        link.save()
        metadata['booking_payment_link_id'] = str(link.pk)
        contact = getattr(booking, 'contact', None)
        customer_email = ''
        if contact is not None:
            customer_email = (getattr(contact, 'email', None) or '').strip()
        session = create_quotation_payment_session(
            sub_account_id=sub_account_id,
            reference_id=reference_id,
            description=f'Payment for booking {booking.unique_id or booking.title}',
            amount_php=pricing.charge_amount,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
            customer_email=customer_email,
        )
    except XenditError as exc:
        link.delete()
        raise PaymentLinkError(str(exc)) from exc

    link.xendit_payment_session_id = xendit_session_id(session)
    link.xendit_checkout_url = payment_link_url(session)
    if not link.xendit_checkout_url:
        link.delete()
        raise PaymentLinkError('Xendit did not return a checkout URL.')
    link.save(
        update_fields=[
            'xendit_payment_session_id',
            'xendit_checkout_url',
            'updated_at',
        ],
    )
    return link


def create_booking_payment_link(
    booking: Quotation,
    *,
    charge_base_amount=None,
    created_by=None,
    expires_in_days: int = 14,
    payment_provider: str | None = None,
) -> QuotationPaymentLink:
    company = _load_company(booking)
    available = verified_payment_providers(company)
    if not available:
        raise PaymentLinkError(
            'No verified payment providers are available. Complete business verification first.',
        )
    try:
        provider = normalize_payment_provider(payment_provider, company=company)
    except ValueError as exc:
        raise PaymentLinkError(str(exc)) from exc
    try:
        assert_payment_provider_link_ready(company, provider)
    except ValueError as exc:
        raise PaymentLinkError(str(exc)) from exc

    sync_quotation_total_amount(booking)
    booking.refresh_from_db(fields=['total_amount', 'updated_at'])

    base_amount = _resolve_base_amount(booking, charge_base_amount)
    try:
        pricing = compute_payment_link_pricing(base_amount)
    except ValueError as exc:
        raise PaymentLinkError(str(exc)) from exc

    token = uuid.uuid4()
    expires_at = timezone.now() + timedelta(days=expires_in_days)

    if provider == PROVIDER_XENDIT:
        success_url, cancel_url, public_url = xendit_payment_return_urls(token)
    else:
        public_url = public_payment_url(token)
        success_url = f'{public_url}?status=success'
        cancel_url = f'{public_url}?status=cancelled'

    if provider == PROVIDER_XENDIT:
        return _create_xendit_link(
            booking,
            company=company,
            pricing=pricing,
            token=token,
            expires_at=expires_at,
            public_url=public_url,
            success_url=success_url,
            cancel_url=cancel_url,
            created_by=created_by,
        )

    return _create_paymongo_link(
        booking,
        company=company,
        pricing=pricing,
        token=token,
        expires_at=expires_at,
        public_url=public_url,
        success_url=success_url,
        cancel_url=cancel_url,
        created_by=created_by,
    )


def provider_checkout_url(link: QuotationPaymentLink) -> str:
    if link.payment_provider == QuotationPaymentLink.PaymentProvider.XENDIT:
        return (link.xendit_checkout_url or '').strip()
    return (link.paymongo_checkout_url or '').strip()


def serialize_public_payment_link(link: QuotationPaymentLink) -> dict:
    booking = link.quotation
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
    expired = link.expires_at < timezone.now() and link.status == QuotationPaymentLink.Status.PENDING
    checkout_url = ''
    if link.status == QuotationPaymentLink.Status.PENDING and not expired:
        checkout_url = provider_checkout_url(link)
    if link.payment_provider == QuotationPaymentLink.PaymentProvider.XENDIT:
        try:
            _, _, pay_public_url = xendit_payment_return_urls(link.public_token)
        except PaymentLinkError:
            pay_public_url = public_payment_url(link.public_token)
    else:
        pay_public_url = public_payment_url(link.public_token)
    return {
        'token': str(link.public_token),
        'status': QuotationPaymentLink.Status.EXPIRED if expired else link.status,
        'quotation_title': booking.title,
        'booking_unique_id': booking.unique_id,
        'company_name': company.name if company else '',
        'payment_provider': link.payment_provider,
        'payment_provider_label': PROVIDER_LABELS.get(link.payment_provider, link.payment_provider.title()),
        'currency': currency_code,
        'currency_symbol': currency_symbol,
        'base_amount': str(link.base_amount),
        'platform_fee': str(link.platform_fee),
        'processing_fee_estimate': str(link.processing_fee_estimate),
        'charge_amount': str(link.charge_amount),
        'fees_total': str(pricing.fees_total),
        'checkout_url': checkout_url,
        'public_url': pay_public_url,
        'expires_at': link.expires_at.isoformat(),
        'paid_at': link.paid_at.isoformat() if link.paid_at else None,
    }
