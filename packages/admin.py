from django.contrib import admin

from .models import Package, PackageItem, PackageVersion


class PackageItemInline(admin.TabularInline):
    model = PackageItem
    extra = 0
    raw_id_fields = ('company', 'account', 'created_by')


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'package_version',
        'company',
        'account',
        'total_price',
        'is_active',
        'created_at',
        'deleted_at',
    )
    list_filter = ('is_active', 'account', 'package_version')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)
    raw_id_fields = ('package_version', 'company', 'account', 'created_by')
    inlines = [PackageItemInline]


@admin.register(PackageItem)
class PackageItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'package',
        'parent',
        'company',
        'price',
        'sort_order',
        'is_active',
        'created_at',
        'deleted_at',
    )
    list_filter = ('is_active', 'account', 'package')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)
    raw_id_fields = ('package', 'parent', 'company', 'account', 'created_by')


@admin.register(PackageVersion)
class PackageVersionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'effectivity_date',
        'company',
        'is_active',
        'created_at',
        'deleted_at',
    )
    list_filter = ('is_active', 'account')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)
    raw_id_fields = ('company', 'account', 'created_by')
