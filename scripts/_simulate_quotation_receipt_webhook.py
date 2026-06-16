"""One-off: simulate payment.paid webhook for quotation 26-0001."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import django

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planningwithyou.settings')
django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402
from django.test import Client, override_settings  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils import timezone  # noqa: E402

from bookings.models import (  # noqa: E402
    Quotation,
    QuotationPayment,
    QuotationPaymentLink,
    QuotationPaymentReceipt,
)
from bookings.payment_pricing import amount_to_centavos, compute_payment_link_pricing  # noqa: E402
from bookings.payment_receipts import notify_payment_received  # noqa: E402
from contacts.models import Contact  # noqa: E402
from emails.mail import send_email  # noqa: E402
from emails.models import EmailLog  # noqa: E402

UNIQUE_ID = '26-0001'
CONTACT_EMAIL = 'rpascual0812@gmail.com'
PAYMENT_ID = 'pay_sim_quotation_26_0001_001'
EVENT_ID = 'evt_sim_quotation_26_0001_001'


def paymongo_signature(payload: bytes, secret: str) -> str:
    timestamp = str(int(time.time()))
    signed = f'{timestamp}.{payload.decode("utf-8")}'.encode('utf-8')
    digest = hmac.new(secret.encode('utf-8'), signed, hashlib.sha256).hexdigest()
    return f't={timestamp},te={digest},li='


def ensure_contact_email(quotation: Quotation) -> None:
    if quotation.contact_id:
        contact = quotation.contact
        contact.email = CONTACT_EMAIL
        contact.save(update_fields=['email', 'updated_at'])
        print(f'Updated contact id={contact.pk} email -> {CONTACT_EMAIL}')
        return

    contact = Contact.objects.create(
        account_id=quotation.account_id,
        company_org_id=quotation.company_id,
        first_name='Rafael',
        last_name='Pascual',
        email=CONTACT_EMAIL,
    )
    quotation.contact = contact
    quotation.save(update_fields=['contact_id', 'updated_at'])
    print(f'Created contact id={contact.pk} and linked to quotation {quotation.pk}')


def find_or_create_pending_link(quotation: Quotation) -> QuotationPaymentLink:
    now = timezone.now()
    link = (
        QuotationPaymentLink.objects.filter(
            quotation_id=quotation.pk,
            status=QuotationPaymentLink.Status.PENDING,
            expires_at__gt=now,
        )
        .order_by('-id')
        .first()
    )
    if link is not None:
        print(
            f'Using pending link id={link.pk} base={link.base_amount} charge={link.charge_amount}',
        )
        return link

    base_amount = quotation.required_downpayment_amount or Decimal('0')
    if base_amount <= Decimal('0'):
        raise SystemExit('ERROR: quotation has no required_downpayment_amount for new link')

    pricing = compute_payment_link_pricing(base_amount)
    link = QuotationPaymentLink.objects.create(
        quotation=quotation,
        account_id=quotation.account_id,
        company_id=quotation.company_id,
        public_token=uuid.uuid4(),
        base_amount=pricing.base_amount,
        platform_fee=pricing.platform_fee,
        processing_fee_estimate=pricing.processing_fee_estimate,
        charge_amount=pricing.charge_amount,
        currency='PHP',
        status=QuotationPaymentLink.Status.PENDING,
        expires_at=now + timedelta(days=14),
        paymongo_checkout_session_id=f'cs_sim_{quotation.unique_id}',
    )
    print(
        f'Created pending link id={link.pk} base={link.base_amount} charge={link.charge_amount}',
    )
    return link


def payment_paid_payload(link: QuotationPaymentLink) -> dict:
    amount_centavos = amount_to_centavos(link.charge_amount)
    metadata = {
        'booking_payment_link_id': str(link.pk),
        'quotation_id': str(link.quotation_id),
        'account_id': str(link.account_id),
        'company_id': str(link.company_id),
    }
    return {
        'data': {
            'id': EVENT_ID,
            'type': 'event',
            'attributes': {
                'type': 'payment.paid',
                'data': {
                    'id': PAYMENT_ID,
                    'type': 'payment',
                    'attributes': {
                        'status': 'paid',
                        'amount': amount_centavos,
                        'currency': 'PHP',
                        'metadata': metadata,
                        'payment_method_type': 'gcash',
                    },
                },
            },
        },
    }


def cleanup_prior_simulation(quotation_id: int) -> None:
    for payment in QuotationPayment.objects.filter(
        quotation_id=quotation_id,
        transaction_id=PAYMENT_ID,
        deleted_at__isnull=True,
    ):
        QuotationPaymentReceipt.objects.filter(quotation_payment_id=payment.pk).delete()
        payment.delete()
        print(f'Removed prior simulation payment id={payment.pk}')


def main() -> int:
    secret = (getattr(settings, 'PAYMONGO_WEBHOOK_SECRET', None) or '').strip()
    if not secret:
        print('ERROR: PAYMONGO_WEBHOOK_SECRET is not set')
        return 1

    quotation = (
        Quotation.objects.filter(unique_id=UNIQUE_ID)
        .select_related('contact', 'created_by', 'company')
        .first()
    )
    if quotation is None:
        print(f'ERROR: Quotation {UNIQUE_ID} not found')
        return 1

    print(
        f'Quotation id={quotation.pk} account={quotation.account_id} '
        f'company={quotation.company_id} title={quotation.title!r}',
    )

    ensure_contact_email(quotation)
    quotation.refresh_from_db()

    link = find_or_create_pending_link(quotation)
    cleanup_prior_simulation(quotation.pk)

    payload = payment_paid_payload(link)
    raw = json.dumps(payload).encode('utf-8')
    sig = paymongo_signature(raw, secret)

    client = Client()
    with override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1']):
        response = client.post(
            reverse('paymongo-webhook'),
            data=raw,
            content_type='application/json',
            HTTP_PAYMONGO_SIGNATURE=sig,
        )
    print(f'Webhook response: {response.status_code} {response.content.decode()}')

    if response.status_code != 200:
        return 1

    transaction.get_connection().run_and_clear_commit_hooks()

    payment = QuotationPayment.objects.filter(
        quotation_id=quotation.pk,
        transaction_id=PAYMENT_ID,
        deleted_at__isnull=True,
    ).first()
    if payment is None:
        print('ERROR: QuotationPayment was not created')
        return 1

    print(
        f'Payment id={payment.pk} status={payment.transaction_status} '
        f'charge={payment.charge_amount} base={payment.base_amount}',
    )

    link.refresh_from_db()
    print(f'Link id={link.pk} status={link.status} paid_at={link.paid_at}')

    receipt = QuotationPaymentReceipt.objects.filter(quotation_payment_id=payment.pk).first()
    if receipt is None:
        print('ERROR: QuotationPaymentReceipt was not created')
        return 1

    print(f'Receipt id={receipt.pk} emailed_at={receipt.emailed_at} url={bool(receipt.receipt_url)}')

    if receipt.emailed_at is not None:
        receipt.emailed_at = None
        receipt.save(update_fields=['emailed_at', 'updated_at'])
        print('Cleared receipt.emailed_at for contact notification')

    notify_payment_received(payment, use_contact_email=True)
    receipt.refresh_from_db()
    print(f'After notify: receipt emailed_at={receipt.emailed_at}')

    log = (
        EmailLog.objects.filter(account_id=quotation.account_id, to__icontains=CONTACT_EMAIL)
        .order_by('-id')
        .first()
    )
    if log is None:
        log = EmailLog.objects.filter(account_id=quotation.account_id).order_by('-id').first()
    if log is None:
        print('ERROR: EmailLog was not created')
        return 1

    print(f'EmailLog id={log.pk} to={log.to} subject={log.subject}')

    try:
        send_email(log.pk)
        print(f'Email sent synchronously to {CONTACT_EMAIL}')
    except Exception as exc:
        print(f'ERROR sending email: {exc}')
        return 1

    receipt.refresh_from_db()
    print(f'Done. Receipt emailed_at={receipt.emailed_at}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
