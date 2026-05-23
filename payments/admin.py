from django.contrib import admin

from .models import PaymentIntegration


@admin.register(PaymentIntegration)
class PaymentIntegrationAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'company',
        'payment_gateway',
        'created_at',
        'deleted_at',
    ]
    list_filter = ['payment_gateway', 'deleted_at']
    search_fields = ['company__name']
    raw_id_fields = ['company', 'account', 'created_by']
    readonly_fields = ['created_at', 'updated_at']
