"""Record off-platform (manual) quotation payments."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.utils import timezone

from .models import Quotation, QuotationPayment
from .payment_receipts import notify_payment_received
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
    return payment
