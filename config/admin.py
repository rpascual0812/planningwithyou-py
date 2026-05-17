from django.contrib import admin

from .models import Config


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'account', 'scope', 'name', 'value', 'created_at')
    list_filter = ('scope', 'account')
    search_fields = ('scope', 'name', 'value')
    ordering = ('scope', 'name')
    readonly_fields = ('created_at',)
