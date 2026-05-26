from django.conf import settings
from django.db import models
from django.utils import timezone


class SystemNotificationQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class SystemNotificationManager(models.Manager.from_queryset(SystemNotificationQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SystemNotificationAllManager(models.Manager.from_queryset(SystemNotificationQuerySet)):
    pass


class SystemNotification(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='system_notifications_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SystemNotificationManager()
    all_objects = SystemNotificationAllManager()

    class Meta:
        db_table = 'system_notifications'
        ordering = ['-start_date', '-id']

    def __str__(self):
        return self.title

    @property
    def is_active_now(self) -> bool:
        now = timezone.now()
        return self.start_date <= now <= self.end_date
