from django.contrib import admin

from .models import Config, ErrorLog


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'account', 'company', 'scope', 'name', 'value', 'created_at')
    list_filter = ('scope', 'account', 'company')
    search_fields = ('scope', 'name', 'value')
    ordering = ('scope', 'name')
    readonly_fields = ('created_at',)


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'created_at',
        'method',
        'path',
        'status_code',
        'exception_type',
        'user',
        'account',
    )
    list_filter = ('method', 'status_code', 'exception_type')
    search_fields = ('path', 'exception_message', 'exception_type')
    readonly_fields = (
        'method',
        'path',
        'query_string',
        'status_code',
        'exception_type',
        'exception_message',
        'traceback',
        'request_body',
        'user',
        'account',
        'ip_address',
        'user_agent',
        'created_at',
    )
    ordering = ('-created_at',)
