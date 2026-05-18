from celery import shared_task
from django.db import transaction

from .models import BookingItem
from .pdf_build import build_booking_pdf, delete_booking_pdf_file


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_booking_pdf_task(self, booking_id: int):
    try:
        booking = (
            BookingItem.objects.select_related(
                'status', 'account', 'account__country', 'contact',
            ).prefetch_related(
                'contact__phone_numbers', 'contact__addresses',
            )
            .prefetch_related('lines__booking_group')
            .get(pk=booking_id)
        )
        with transaction.atomic():
            locked = BookingItem.objects.select_for_update().get(pk=booking_id)
            old_path = locked.pdf
            file_path = build_booking_pdf(locked)
            if old_path and old_path != file_path:
                delete_booking_pdf_file(old_path)
            locked.pdf = file_path
            locked.save(update_fields=['pdf', 'updated_at'])
    except BookingItem.DoesNotExist:
        return
    except Exception as exc:
        raise self.retry(exc=exc)
