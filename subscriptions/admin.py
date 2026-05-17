from django.contrib import admin

from .models import AccountSubscription, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'plan',
        'name',
        'billing_cycle',
        'base_price',
        'price_per_user',
        'is_active',
        'is_selectable',
        'sort_order',
    )
    list_filter = ('billing_cycle', 'is_active', 'has_team_stepper')
    search_fields = ('plan', 'name', 'subtitle')
    ordering = ('sort_order', 'plan', 'billing_cycle')


@admin.register(AccountSubscription)
class AccountSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'uuid',
        'account',
        'subscription',
        'reference_id',
        'start_date',
        'end_date',
        'total_price',
        'deleted_at',
    )
    list_filter = ('start_date', 'deleted_at')
    search_fields = ('uuid', 'reference_id', 'account__name', 'discount_code')
    readonly_fields = ('uuid', 'created_at', 'updated_at')
    raw_id_fields = ('account', 'subscription')
    date_hierarchy = 'start_date'
