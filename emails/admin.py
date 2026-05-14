from django.contrib import admin

from .models import EmailLog, EmailTemplate


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'to', 'email_from', 'subject', 'status', 'created_at', 'sent_at')
    list_filter = ('status',)
    search_fields = ('to', 'subject', 'email_from')
    readonly_fields = ('created_at', 'sent_at')


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'title', 'subject', 'template_type', 'is_active', 'deleted_at', 'updated_at')
    list_filter = ('template_type', 'is_active')
    search_fields = ('name', 'title', 'subject', 'body')
