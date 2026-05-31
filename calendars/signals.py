"""Sync calendar events with Google Calendar after DB commits."""

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .google_calendar_service import (
    delete_event_from_google,
    push_event_to_google,
    skip_google_sync,
)
from .models import Calendar


def _push_after_commit(event_id: int) -> None:
    event = Calendar.objects.filter(pk=event_id, deleted_at__isnull=True).first()
    if event is not None:
        push_event_to_google(event)


def _delete_after_commit(event_id: int) -> None:
    event = Calendar.all_objects.filter(pk=event_id).first()
    if event is not None:
        delete_event_from_google(event)


@receiver(post_save, sender=Calendar)
def sync_calendar_with_google(sender, instance: Calendar, **kwargs) -> None:
    if skip_google_sync.get():
        return
    if instance.deleted_at is not None:
        transaction.on_commit(lambda: _delete_after_commit(instance.pk))
        return
    transaction.on_commit(lambda: _push_after_commit(instance.pk))
