"""User lifecycle signals."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .jwt import invalidate_user_session

User = get_user_model()


@receiver(pre_save, sender=User)
def track_account_restricted_change(sender, instance, **kwargs):
    if not instance.pk:
        instance._was_account_restricted = False  # noqa: SLF001
        return
    previous = (
        User.objects.filter(pk=instance.pk)
        .values_list('account_restricted', flat=True)
        .first()
    )
    instance._was_account_restricted = bool(previous)  # noqa: SLF001


@receiver(post_save, sender=User)
def revoke_session_when_account_restricted(sender, instance, **kwargs):
    was_restricted = getattr(instance, '_was_account_restricted', False)
    if instance.account_restricted and not was_restricted:
        invalidate_user_session(instance)
