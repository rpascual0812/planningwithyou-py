from celery import shared_task
from django.db import transaction

from planningwithyou.file_storage import booking_pdf_download_path

from .models import Quotation
from .pdf_build import build_booking_pdf


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_booking_pdf_task(self, quotation_id: int):
    try:
        booking = (
            Quotation.objects.select_related(
                'status',
                'account',
                'account__country',
                'contact',
                'created_by',
            ).prefetch_related(
                'contact__phone_numbers', 'contact__addresses',
            )
            .prefetch_related(
                'lines__quotation_group',
                'lines__company',
                'lines__package',
                'lines__package_version',
            )
            .get(pk=quotation_id)
        )
        with transaction.atomic():
            locked = Quotation.objects.select_for_update().get(pk=quotation_id)
            build_booking_pdf(booking)
            locked.pdf = booking_pdf_download_path(locked.pk)
            locked.save(update_fields=['pdf', 'updated_at'])
    except Quotation.DoesNotExist:
        return
    except Exception as exc:
        raise self.retry(exc=exc)
