"""Record off-platform (manual) quotation payments."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.utils import timezone

from .models import Quotation, QuotationPayment
from .payment_breakdown import booking_payments_paid_base_total
from .payment_receipts import notify_payment_received
from .notifications import schedule_payment_link_email
from .scope import assert_booking_editable


def create_manual_quotation_payment(
    quotation: Quotation,
    *,
    amount: Decimal,
    payment_method: str,
    notes: str = '',
) -> QuotationPayment:
    assert amount > Decimal('0')
    now = timezone.now()
    payment = QuotationPayment.objects.create(
        quotation=quotation,
        account_id=quotation.account_id,
        company_id=quotation.company_id,
        payment_method=payment_method,
        amount=amount,
        charge_amount=amount,
        base_amount=amount,
        net_amount=amount,
        platform_fee=Decimal('0'),
        processing_fee=Decimal('0'),
        tax=Decimal('0'),
        transaction_id=str(uuid.uuid4()),
        transaction_status='paid',
        notes=(notes or '').strip(),
        transaction_date=now,
        payout_sent_at=now,
    )
    notify_payment_received(payment, use_contact_email=True)
    schedule_payment_link_email(
        quotation.pk,
        actor_id=getattr(quotation.created_by, 'pk', None),
    )
    return payment


def create_manual_quotation_refund(
    quotation: Quotation,
    *,
    amount: Decimal,
    payment_method: str,
    notes: str = '',
) -> QuotationPayment:
    paid = booking_payments_paid_base_total(quotation.pk)
    if amount > paid:
        raise ValueError(
            f'Refund amount cannot exceed {paid} already paid on this quotation.',
        )
    now = timezone.now()
    payment = QuotationPayment.objects.create(
        quotation=quotation,
        account_id=quotation.account_id,
        company_id=quotation.company_id,
        payment_method=payment_method,
        amount=amount,
        charge_amount=amount,
        base_amount=amount,
        net_amount=amount,
        platform_fee=Decimal('0'),
        processing_fee=Decimal('0'),
        tax=Decimal('0'),
        transaction_id=str(uuid.uuid4()),
        transaction_status='refunded',
        notes=(notes or '').strip(),
        transaction_date=now,
        payout_sent_at=None,
    )
    schedule_payment_link_email(
        quotation.pk,
        actor_id=getattr(quotation.created_by, 'pk', None),
    )
    return payment
