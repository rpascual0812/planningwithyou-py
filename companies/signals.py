"""Activate company timezone before ORM insert/update."""

from __future__ import annotations

from django.core.exceptions import FieldDoesNotExist
from django.db.models.signals import pre_save
from django.dispatch import receiver

from companies.timezone import (
    activate_timezone_for_instance,
    company_id_for_instance,
    now_in_company_timezone,
)


@receiver(pre_save)
def apply_company_timezone_before_save(sender, instance, **kwargs):
    """
    Before each save, switch to ``companies.timezone`` for the record's company
    and set ``created_at`` on insert when it is not managed by ``auto_now_add``.
    """
    activate_timezone_for_instance(instance)
    if not instance._state.adding:
        return
    company_id = company_id_for_instance(instance)
    try:
        field = instance._meta.get_field('created_at')
    except FieldDoesNotExist:
        return
    if field.auto_now or field.auto_now_add:
        return
    if getattr(instance, 'created_at', None) is None:
        instance.created_at = now_in_company_timezone(company_id)
