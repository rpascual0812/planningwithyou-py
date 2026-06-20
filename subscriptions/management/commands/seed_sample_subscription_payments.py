"""Create sample subscription payments and PDF receipts for an account."""

from __future__ import annotations

from datetime import datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from subscriptions.models import AccountSubscription, SubscriptionPayment
from subscriptions.proration import add_months
from subscriptions.subscription_receipts import ensure_subscription_payment_receipt


class Command(BaseCommand):
    help = (
        'Create sample SubscriptionPayment rows (and PDF receipts) for the past '
        'N billing periods, based on the account’s current account_subscriptions row.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            default=1,
            help='Account id (default: 1)',
        )
        parser.add_argument(
            '--months',
            type=int,
            default=2,
            help='How many past billing periods to seed (default: 2)',
        )
        parser.add_argument(
            '--send-email',
            action='store_true',
            help='Email receipts to account.contact_email (default: skip)',
        )

    def handle(self, *args, **options):
        account_id = options['account_id']
        months = max(1, options['months'])
        send_email = options['send_email']

        account_sub = (
            AccountSubscription.objects.filter(
                account_id=account_id,
                deleted_at__isnull=True,
            )
            .select_related('subscription', 'account')
            .order_by('-start_date', '-id')
            .first()
        )
        if account_sub is None:
            raise CommandError(
                f'No active account_subscriptions row for account_id={account_id}.',
            )

        plan_name = account_sub.subscription.name
        anchor = account_sub.start_date
        tz = timezone.get_current_timezone()
        created = 0
        skipped = 0

        for offset in range(months, 0, -1):
            period_start = add_months(anchor, -offset)
            period_end = add_months(anchor, -(offset - 1))
            invoice_key = f'sample-seed-{account_id}-{period_start.isoformat()}'

            if SubscriptionPayment.objects.filter(
                paymongo_invoice_id=invoice_key,
            ).exists():
                skipped += 1
                self.stdout.write(f'Skip existing sample payment {period_start}')
                continue

            paid_at = timezone.make_aware(
                datetime.combine(period_start, time(hour=10, minute=0)),
                tz,
            )
            payment = SubscriptionPayment.objects.create(
                account_id=account_id,
                account_subscription=account_sub,
                amount=account_sub.total_price,
                currency='PHP',
                paid_at=paid_at,
                paymongo_invoice_id=invoice_key,
                paymongo_payment_id=f'sample-pay-{invoice_key}',
                period_start=period_start,
                period_end=period_end,
                description=f'{plan_name} subscription ({period_start:%b %Y})',
            )
            receipt = ensure_subscription_payment_receipt(
                payment.pk,
                send_email=send_email,
            )
            created += 1
            receipt_no = receipt.receipt_number if receipt else '—'
            self.stdout.write(
                self.style.SUCCESS(
                    f'Payment {payment.pk} {period_start} to {period_end} '
                    f'amount={payment.amount} receipt={receipt_no}',
                ),
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Done: {created} created, {skipped} skipped for account_id={account_id}.',
            ),
        )
