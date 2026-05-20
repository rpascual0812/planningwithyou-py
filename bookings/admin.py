from django.contrib import admin

from .models import (
    BookingItem,
    BookingStatus,
    BookingUniqueIdSequence,
    FormTemplate,
    FormTemplateField,
    FormTemplateFieldOption,
)


class BookingItemInline(admin.TabularInline):
    model = BookingItem
    extra = 0
    ordering = ['sort_order', 'id']


@admin.register(BookingStatus)
class BookingStatusAdmin(admin.ModelAdmin):
    list_display = ['title', 'color', 'sort_order', 'created_at']
    ordering = ['sort_order', 'id']
    inlines = [BookingItemInline]


@admin.register(BookingUniqueIdSequence)
class BookingUniqueIdSequenceAdmin(admin.ModelAdmin):
    list_display = ['account_id', 'year', 'last_sequence']
    list_filter = ['year']


@admin.register(BookingItem)
class BookingItemAdmin(admin.ModelAdmin):
    list_display = ['unique_id', 'title', 'status', 'created_by', 'sort_order', 'created_at']
    search_fields = ['unique_id', 'title']
    list_filter = ['status']
    ordering = ['sort_order', 'id']


class FormTemplateFieldOptionInline(admin.TabularInline):
    model = FormTemplateFieldOption
    extra = 1
    ordering = ['sort_order', 'id']


@admin.register(FormTemplateField)
class FormTemplateFieldAdmin(admin.ModelAdmin):
    list_display = ['label', 'template', 'field_type', 'is_required', 'price', 'sort_order']
    list_filter = ['field_type', 'is_required']
    inlines = [FormTemplateFieldOptionInline]


class FormTemplateFieldInline(admin.TabularInline):
    model = FormTemplateField
    extra = 1
    ordering = ['sort_order', 'id']
    show_change_link = True


@admin.register(FormTemplate)
class FormTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'company']
    search_fields = ['name']
    inlines = [FormTemplateFieldInline]
