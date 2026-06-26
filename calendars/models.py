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
    quotation = models.ForeignKey(
        'bookings.Quotation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='quotation_id',
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


class AppointmentReminderQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class AppointmentReminderManager(models.Manager.from_queryset(AppointmentReminderQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AppointmentReminderAllManager(models.Manager.from_queryset(AppointmentReminderQuerySet)):
    pass


class AppointmentReminder(models.Model):
    class ReminderType(models.TextChoices):
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'

    class OffsetUnit(models.TextChoices):
        MINUTE = 'minute', 'Minute'
        MINUTES = 'minutes', 'Minutes'
        HOUR = 'hour', 'Hour'
        HOURS = 'hours', 'Hours'
        DAY = 'day', 'Day'
        DAYS = 'days', 'Days'
        WEEK = 'week', 'Week'
        WEEKS = 'weeks', 'Weeks'

    class CalendarAnchor(models.TextChoices):
        START = 'start', 'Before event start'
        END = 'end', 'Before event end'

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='appointment_reminders',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='appointment_reminders',
    )
    calendar_statuses = models.ManyToManyField(
        CalendarStatus,
        related_name='appointment_reminders',
        blank=True,
    )
    calendar = models.CharField(
        max_length=16,
        choices=CalendarAnchor.choices,
        default=CalendarAnchor.START,
        help_text='Which calendar event time the offset is measured from.',
    )
    frequency = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=16, choices=OffsetUnit.choices, default=OffsetUnit.HOURS)
    reminder_type = models.CharField(
        max_length=8,
        choices=ReminderType.choices,
        default=ReminderType.EMAIL,
        db_column='type',
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointment_reminders_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = AppointmentReminderManager()
    all_objects = AppointmentReminderAllManager()

    class Meta:
        db_table = 'appointment_reminders'
        ordering = ['id']

    def __str__(self):
        return f'Reminder {self.frequency} {self.unit} ({self.reminder_type})'


class ScheduledAppointmentReminderQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class ScheduledAppointmentReminderManager(
    models.Manager.from_queryset(ScheduledAppointmentReminderQuerySet),
):
    def get_queryset(self):
        return super().get_queryset()


class ScheduledAppointmentReminderAllManager(
    models.Manager.from_queryset(ScheduledAppointmentReminderQuerySet),
):
    pass


class ScheduledAppointmentReminder(models.Model):
    """A single scheduled reminder email for a calendar event recipient."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    class RecipientRole(models.TextChoices):
        CONTACT = 'contact', 'Contact'
        AUTHOR = 'author', 'Author'

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='scheduled_appointment_reminders',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='scheduled_appointment_reminders',
    )
    calendar_event = models.ForeignKey(
        Calendar,
        on_delete=models.CASCADE,
        db_column='calendar_event_id',
        related_name='scheduled_reminders',
    )
    appointment_reminder = models.ForeignKey(
        AppointmentReminder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='appointment_reminder_id',
        related_name='scheduled_sends',
    )
    recipient_role = models.CharField(
        max_length=16,
        choices=RecipientRole.choices,
    )
    recipient_email = models.EmailField(max_length=255)
    recipient_name = models.CharField(max_length=255, blank=True, default='')
    send_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    email_log = models.ForeignKey(
        'emails.EmailLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='email_log_id',
        related_name='scheduled_appointment_reminders',
    )
    error = models.TextField(blank=True, default='')
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ScheduledAppointmentReminderManager()
    all_objects = ScheduledAppointmentReminderAllManager()

    class Meta:
        db_table = 'scheduled_appointment_reminders'
        ordering = ['-send_at', 'id']
        indexes = [
            models.Index(
                fields=['status', 'send_at'],
                name='sched_appt_rem_status_send',
            ),
        ]

    def __str__(self):
        return (
            f'Reminder to {self.recipient_email} at {self.send_at} '
            f'[{self.status}]'
        )
