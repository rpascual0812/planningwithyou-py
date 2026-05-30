"""Emails for successful (receipt) and failed subscription payments."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from emails.mail import create_and_queue_email
from emails.tasks import send_email_task

from .models import (
    AccountSubscription,
    SubscriptionFailedPaymentNotice,
    SubscriptionPayment,
    SubscriptionReceipt,
)


def _currency(amount: Decimal) -> str:
    return f'PHP {amount:.2f}'


def _settings_subscription_url() -> str:
    base = (getattr(settings, 'FRONTEND_URL', None) or '').rstrip('/')
    return f'{base}/settings?tab=subscription'


def _settings_receipts_url() -> str:
    base = (getattr(settings, 'FRONTEND_URL', None) or '').rstrip('/')
    return f'{base}/settings?tab=account&section=receipts'


def _contact_email(account_sub: AccountSubscription) -> str:
    return (account_sub.account.contact_email or '').strip()


def invoice_indicates_successful_payment(attrs: dict, *, event_type: str) -> bool:
    """True when PayMongo reports a completed subscription invoice charge."""
    if event_type != 'subscription.invoice.paid':
        return False
    status = (attrs.get('status') or '').strip().lower()
    if not status:
        return True
    return status in {'paid', 'succeeded', 'success', 'completed'}


def invoice_indicates_failed_payment(event_type: str) -> bool:
    return event_type == 'subscription.invoice.payment_failed'


def issue_subscription_payment_receipt(payment_id: int) -> SubscriptionReceipt | None:
    """
    Generate a PDF receipt and email ``account.contact_email`` after a successful
    subscription payment. No-op if the payment row does not exist.
    """
    from .subscription_receipts import ensure_subscription_payment_receipt

    return ensure_subscription_payment_receipt(payment_id)


def notify_subscription_payment_failed(
    account_sub: AccountSubscription,
    *,
    invoice_id: str,
    amount: Decimal | None = None,
) -> bool:
    """
    Email ``account.contact_email`` that a subscription charge failed.
    Sends at most once per PayMongo invoice id.
    """
    invoice_key = (invoice_id or '').strip()
    if not invoice_key:
        invoice_key = f'failed-{account_sub.pk}-{int(timezone.now().timestamp())}'

    recipient = _contact_email(account_sub)
    if not recipient:
        return False

    notice, created = SubscriptionFailedPaymentNotice.objects.get_or_create(
        account_id=account_sub.account_id,
        paymongo_invoice_id=invoice_key,
        defaults={
            'amount': amount if amount is not None else account_sub.total_price,
        },
    )
    if not created and notice.emailed_at is not None:
        return False

    plan_name = account_sub.subscription.name
    charge = notice.amount if notice.amount is not None else account_sub.total_price
    settings_url = _settings_subscription_url()
    subject = f'Subscription payment failed – {plan_name}'
    body = (
        '<p>Hello,</p>'
        f'<p>We could not process your subscription payment of '
        f'<strong>{_currency(charge)}</strong> for <strong>{plan_name}</strong>.</p>'
        '<p>Your subscription may be marked past due until payment succeeds. '
        'Please update your payment method or retry billing in PayMongo.</p>'
        f'<p><a href="{settings_url}">Open subscription settings</a></p>'
        '<p>If you need help, reply to this email or contact support.</p>'
    )
    log = create_and_queue_email(
        to=[recipient],
        subject=subject,
        body=body,
        account=account_sub.account,
        company=None,
        created_by=None,
    )
    send_email_task.delay(log.pk)
    notice.emailed_at = timezone.now()
    notice.save(update_fields=['emailed_at'])
    return True


def payment_qualifies_for_receipt(payment: SubscriptionPayment) -> bool:
    """Receipts are only issued for recorded successful charges."""
    return payment.paid_at is not None and payment.amount >= 0
