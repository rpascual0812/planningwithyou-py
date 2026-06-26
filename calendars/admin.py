from django.contrib import admin

from .models import AppointmentReminder, Calendar, CalendarStatus, ScheduledAppointmentReminder


@admin.register(CalendarStatus)
class CalendarStatusAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'text_color',
        'background_color',
        'sort_order',
        'account_id',
        'created_by',
        'created_at',
        'deleted_at',
    )
    list_filter = ('deleted_at',)
    search_fields = ('title',)
    ordering = ('sort_order', 'id')


@admin.register(Calendar)
class CalendarAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'start',
        'end',
        'status',
        'contact',
        'quotation',
        'company',
        'account',
        'created_by',
        'created_at',
        'deleted_at',
    )
    list_filter = ('deleted_at',)
    search_fields = ('title',)
    ordering = ('start', 'id')


@admin.register(AppointmentReminder)
class AppointmentReminderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'company',
        'calendar',
        'frequency',
        'unit',
        'reminder_type',
        'is_active',
        'account',
        'created_at',
        'deleted_at',
    )
    list_filter = ('reminder_type', 'calendar', 'unit', 'is_active', 'deleted_at')
    filter_horizontal = ('calendar_statuses',)
    ordering = ('id',)


@admin.register(ScheduledAppointmentReminder)
class ScheduledAppointmentReminderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'calendar_event',
        'recipient_email',
        'recipient_role',
        'send_at',
        'status',
        'company',
        'deleted_at',
    )
    list_filter = ('status', 'recipient_role', 'deleted_at')
    search_fields = ('recipient_email', 'recipient_name', 'calendar_event__title')
    ordering = ('-send_at', 'id')
