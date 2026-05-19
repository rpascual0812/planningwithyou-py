from django.contrib import admin

from .models import SupplierSetting, SupplierSettingTier, SupplierType, Tier


@admin.register(SupplierType)
class SupplierTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_active', 'created_at', 'deleted_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


class SupplierSettingTierInline(admin.TabularInline):
    model = SupplierSettingTier
    extra = 0
    raw_id_fields = ('tier',)


@admin.register(SupplierSetting)
class SupplierSettingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'supplier', 'account', 'is_active', 'created_at', 'updated_at',
    )
    list_filter = ('is_active',)
    search_fields = ('supplier__name', 'account__name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('supplier', 'account')
    inlines = [SupplierSettingTierInline]


@admin.register(Tier)
class TierAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'account', 'company', 'name', 'is_active',
        'created_by', 'created_at', 'deleted_at',
    )
    list_filter = ('is_active', 'account')
    search_fields = ('name',)
    readonly_fields = ('created_at',)
    raw_id_fields = ('account', 'company', 'created_by')


@admin.register(SupplierSettingTier)
class SupplierSettingTierAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'supplier_setting',
        'tier',
        'discount',
        'discount_type',
        'mark_up',
        'mark_up_type',
        'price_override',
        'tax',
        'price',
        'updated_at',
    )
    list_filter = ('discount_type', 'mark_up_type')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('supplier_setting', 'tier')
