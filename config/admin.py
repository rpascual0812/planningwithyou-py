from django.contrib import admin

from .models import Config


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'account', 'company', 'scope', 'name', 'value', 'created_at')
    list_filter = ('scope', 'account', 'company')
    search_fields = ('scope', 'name', 'value')
    ordering = ('scope', 'name')
    readonly_fields = ('created_at',)
