from django.contrib import admin

from .models import Package, SupplierSetting, SupplierSettingPackage, SupplierType


@admin.register(SupplierType)
class SupplierTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_active', 'created_at', 'deleted_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


class SupplierSettingPackageInline(admin.TabularInline):
    model = SupplierSettingPackage
    extra = 0
    raw_id_fields = ('package',)


@admin.register(SupplierSetting)
class SupplierSettingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'supplier', 'account', 'is_active', 'created_at', 'updated_at',
    )
    list_filter = ('is_active',)
    search_fields = ('supplier__name', 'account__name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('supplier', 'account')
    inlines = [SupplierSettingPackageInline]


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'account', 'company', 'name', 'is_active',
        'created_by', 'created_at', 'deleted_at',
    )
    list_filter = ('is_active', 'account')
    search_fields = ('name',)
    readonly_fields = ('created_at',)
    raw_id_fields = ('account', 'company', 'created_by')


@admin.register(SupplierSettingPackage)
class SupplierSettingPackageAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'supplier_setting',
        'package',
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
    raw_id_fields = ('supplier_setting', 'package')
