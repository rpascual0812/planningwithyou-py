from celery import shared_task

from .google_calendar_service import (
    run_full_google_sync,
    schedule_inbound_sync,
)
from .models import GoogleCalendarIntegration


@shared_task
def sync_google_calendar_inbound_task(integration_id: int) -> None:
    schedule_inbound_sync(integration_id)


@shared_task
def backfill_google_calendar_task(integration_id: int) -> None:
    integration = GoogleCalendarIntegration.objects.filter(pk=integration_id).first()
    if integration is None:
        return
    run_full_google_sync(integration)
