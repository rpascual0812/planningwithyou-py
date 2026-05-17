from django.contrib import admin

from .models import Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'iso_code',
        'iso2_code',
        'currency',
        'currency_symbol',
        'currency_code',
    )
    search_fields = ('name', 'iso_code', 'iso2_code', 'currency_code')
    ordering = ('name',)
