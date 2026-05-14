from django.contrib import admin

from .models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'to', 'email_from', 'subject', 'status', 'created_at', 'sent_at')
    list_filter = ('status',)
    search_fields = ('to', 'subject', 'email_from')
    readonly_fields = ('created_at', 'sent_at')
