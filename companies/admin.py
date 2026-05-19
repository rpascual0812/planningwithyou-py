from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'account',
        'is_active',
        'is_main',
        'sort_order',
        'created_at',
    )
    list_filter = ('is_active', 'is_main', 'account')
    search_fields = ('name', 'website')
    readonly_fields = ('created_at',)
    raw_id_fields = ('account', 'created_by')
