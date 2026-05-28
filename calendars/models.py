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
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = CalendarManager()
    all_objects = CalendarAllManager()

    class Meta:
        db_table = 'calendar'
        ordering = ['start', 'id']

    def __str__(self):
        return self.title
