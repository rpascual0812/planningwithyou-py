from django.conf import settings
from django.db import models


class UserNotificationQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def unread(self):
        return self.alive().filter(read_at__isnull=True)


class UserNotificationManager(models.Manager.from_queryset(UserNotificationQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class UserNotificationAllManager(models.Manager.from_queryset(UserNotificationQuerySet)):
    pass


class UserNotification(models.Model):
    class Severity(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'

    class Category(models.TextChoices):
        GENERAL = 'general', 'General'
        GOOGLE_CALENDAR = 'google_calendar', 'Google Calendar'
        GMAIL = 'gmail', 'Gmail'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_notifications',
        db_column='user_id',
    )
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        related_name='user_notifications',
        db_column='account_id',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_notifications',
        db_column='company_id',
    )
    category = models.CharField(
        max_length=32,
        choices=Category.choices,
        default=Category.GENERAL,
        db_index=True,
    )
    severity = models.CharField(
        max_length=16,
        choices=Severity.choices,
        default=Severity.ERROR,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    action_url = models.CharField(max_length=512, blank=True, default='')
    dedupe_key = models.CharField(max_length=255, blank=True, default='', db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserNotificationManager()
    all_objects = UserNotificationAllManager()

    class Meta:
        db_table = 'user_notifications'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(
                fields=['user', 'deleted_at', 'read_at', '-created_at'],
                name='user_notif_user_read_idx',
            ),
        ]

    def __str__(self):
        return f'{self.title} → user={self.user_id}'
