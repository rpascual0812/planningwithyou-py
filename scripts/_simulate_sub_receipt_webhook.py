"""One-off: simulate subscription.invoice.paid webhook for account #2."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

import django

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planningwithyou.settings')
django.setup()

from decimal import Decimal  # noqa: E402

from django.conf import settings  # noqa: E402
from django.test import Client, override_settings  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils import timezone  # noqa: E402

from emails.mail import send_email  # noqa: E402
from emails.models import EmailLog  # noqa: E402
from subscriptions.models import (  # noqa: E402
    AccountSubscription,
    Subscription,
    SubscriptionPayment,
    SubscriptionReceipt,
)
from subscriptions.pricing import compute_subscription_pricing  # noqa: E402
from subscriptions.proration import add_months  # noqa: E402
from users.models import Account  # noqa: E402

ACCOUNT_ID = 2
CONTACT_EMAIL = 'rpascual0812@gmail.com'
TEAM_SEATS = 5  # Pro + 4 additional users
REFERENCE_ID = 'sub_sim_account_2_pro_5seats'
INVOICE_ID = 'inv_sim_account2_pro_5seats_001'


def paymongo_signature(payload: bytes, secret: str) -> str:
    timestamp = str(int(time.time()))
    signed = f'{timestamp}.{payload.decode("utf-8")}'.encode('utf-8')
    digest = hmac.new(secret.encode('utf-8'), signed, hashlib.sha256).hexdigest()
    return f't={timestamp},te={digest},li='


def main() -> int:
    secret = (getattr(settings, 'PAYMONGO_WEBHOOK_SECRET', None) or '').strip()
    if not secret:
        print('ERROR: PAYMONGO_WEBHOOK_SECRET is not set')
        return 1

    account = Account.objects.filter(pk=ACCOUNT_ID).first()
    if account is None:
        print(f'ERROR: Account {ACCOUNT_ID} not found')
        return 1

    account.contact_email = CONTACT_EMAIL
    account.save(update_fields=['contact_email', 'updated_at'])
    print(f'Account {ACCOUNT_ID}: contact_email -> {CONTACT_EMAIL}')

    pro = Subscription.objects.filter(
        plan='pro',
        billing_cycle='monthly',
        is_active=True,
    ).first()
    if pro is None:
        print('ERROR: Pro monthly subscription plan not found')
        return 1

    pricing = compute_subscription_pricing(pro, TEAM_SEATS)
    amount_centavos = int(pricing.total_price * 100)
    print(f'Pro monthly, {TEAM_SEATS} seats: PHP {pricing.total_price} ({amount_centavos} centavos)')

    account_sub = AccountSubscription.objects.filter(
        account_id=ACCOUNT_ID,
        deleted_at__isnull=True,
    ).first()

    today = timezone.localdate()
    if account_sub is None:
        account_sub = AccountSubscription.objects.create(
            account_id=ACCOUNT_ID,
            subscription=pro,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=TEAM_SEATS,
            start_date=today,
            end_date=today,
            base_price=pricing.base_price,
            total_per_users=pricing.total_per_users,
            total_price=pricing.total_price,
            reference_id=REFERENCE_ID,
        )
        print(f'Created AccountSubscription id={account_sub.pk}')
    else:
        account_sub.subscription = pro
        account_sub.status = AccountSubscription.Status.ACTIVE
        account_sub.team_seats = TEAM_SEATS
        account_sub.base_price = pricing.base_price
        account_sub.total_per_users = pricing.total_per_users
        account_sub.total_price = pricing.total_price
        account_sub.reference_id = REFERENCE_ID
        if not account_sub.start_date:
            account_sub.start_date = today
        if not account_sub.end_date:
            account_sub.end_date = today
        account_sub.save()
        print(f'Updated AccountSubscription id={account_sub.pk}, reference_id={REFERENCE_ID}')

    # Remove prior simulation rows so webhook creates fresh payment/receipt.
    old_payments = SubscriptionPayment.objects.filter(
        paymongo_invoice_id=INVOICE_ID,
    )
    for p in old_payments:
        SubscriptionReceipt.objects.filter(payment_id=p.pk).delete()
        p.delete()

    next_billing_date = add_months(today, 1).isoformat()

    payload = {
        'data': {
            'id': 'evt_sim_account2_pro_5seats',
            'type': 'event',
            'attributes': {
                'type': 'subscription.invoice.paid',
                'data': {
                    'id': INVOICE_ID,
                    'type': 'subscription_invoice',
                    'attributes': {
                        'amount': amount_centavos,
                        'subscription_id': REFERENCE_ID,
                        'status': 'paid',
                        'next_billing_schedule': next_billing_date,
                    },
                },
            },
        },
    }

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

    payment = SubscriptionPayment.objects.filter(paymongo_invoice_id=INVOICE_ID).first()
    if payment is None:
        print('ERROR: SubscriptionPayment was not created')
        return 1

    print(f'Payment id={payment.pk}, amount={payment.amount}')

    receipt = SubscriptionReceipt.objects.filter(payment_id=payment.pk).first()
    if receipt is None:
        print('ERROR: SubscriptionReceipt was not created')
        return 1

    print(f'Receipt id={receipt.pk}, number={receipt.receipt_number}, emailed_at={receipt.emailed_at}')

    log = (
        EmailLog.objects.filter(account_id=ACCOUNT_ID)
        .order_by('-id')
        .first()
    )
    if log is None:
        print('ERROR: EmailLog was not created (Celery task may not have run)')
        return 1

    print(f'EmailLog id={log.pk}, to={log.to}, subject={log.subject}')

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
