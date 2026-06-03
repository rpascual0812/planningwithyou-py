from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import QuotationPayment
from .payment_receipts import ensure_paid_booking_payment_receipt


@receiver(post_save, sender=QuotationPayment)
def booking_payment_post_save(sender, instance: QuotationPayment, **kwargs):
    status = (instance.transaction_status or '').strip().lower()
    if status != 'paid':
        return
    transaction.on_commit(
        lambda: ensure_paid_booking_payment_receipt(instance.pk),
    )
