from django.conf import settings
from django.db import models


class CalendarStatusQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class CalendarStatusManager(models.Manager.from_queryset(CalendarStatusQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class CalendarStatusAllManager(models.Manager.from_queryset(CalendarStatusQuerySet)):
    pass


class CalendarStatus(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    text_color = models.CharField(max_length=20, default='#ffffff')
    background_color = models.CharField(max_length=20, default='#1f3a5f')
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calendar_statuses_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = CalendarStatusManager()
    all_objects = CalendarStatusAllManager()

    class Meta:
        db_table = 'calendar_statuses'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.title


class CalendarQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class CalendarManager(models.Manager.from_queryset(CalendarQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class CalendarAllManager(models.Manager.from_queryset(CalendarQuerySet)):
    pass


class Calendar(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
        db_column='company_id',
        related_name='calendar_events',
    )
    status = models.ForeignKey(
        CalendarStatus,
        on_delete=models.PROTECT,
        db_column='status_id',
        related_name='events',
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='contact_id',
        related_name='calendar_events',
    )
    booking = models.ForeignKey(
        'bookings.BookingItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='booking_id',
        related_name='calendar_events',
    )
    title = models.CharField(max_length=255)
    location = models.TextField(blank=True, default='')
    start = models.DateTimeField()
    end = models.DateTimeField()
    repeat_type = models.CharField(max_length=32, null=True, blank=True, default=None)
    repeat_end = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calendar_events_created',
        db_column='created_by',
    )
    google_event_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Google Calendar event id when synced.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = CalendarManager()
    all_objects = CalendarAllManager()

    class Meta:
        db_table = 'calendar'
        ordering = ['start', 'id']

    def __str__(self):
        return self.title


class GoogleCalendarIntegration(models.Model):
    class SyncMode(models.TextChoices):
        ONE_WAY = 'one_way', 'One-way (app → Google)'
        TWO_WAY = 'two_way', 'Two-way'

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='google_calendar_integrations',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='google_calendar_integrations',
    )
    google_email = models.EmailField(max_length=255, blank=True, default='')
    google_calendar_id = models.CharField(
        max_length=255,
        blank=True,
        default='primary',
        help_text='Google calendar id (usually primary).',
    )
    access_token_encrypted = models.TextField(blank=True, default='')
    refresh_token_encrypted = models.TextField(blank=True, default='')
    token_expiry = models.DateTimeField(null=True, blank=True)
    sync_mode = models.CharField(
        max_length=16,
        choices=SyncMode.choices,
        default=SyncMode.ONE_WAY,
    )
    google_sync_token = models.TextField(blank=True, default='')
    watch_channel_id = models.CharField(max_length=255, blank=True, default='')
    watch_resource_id = models.CharField(max_length=255, blank=True, default='')
    watch_channel_token = models.CharField(max_length=64, blank=True, default='')
    watch_expiration = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='google_calendar_integrations_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'google_calendar_integrations'
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'company'],
                name='google_calendar_integrations_one_per_company',
            ),
        ]

    def __str__(self):
        return f'Google Calendar {self.google_email or "—"} company={self.company_id}'
