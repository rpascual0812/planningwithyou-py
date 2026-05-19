from django.contrib import admin

from .models import Calendar, CalendarStatus


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
        'booking',
        'company',
        'account',
        'created_by',
        'created_at',
        'deleted_at',
    )
    list_filter = ('deleted_at',)
    search_fields = ('title',)
    ordering = ('start', 'id')
