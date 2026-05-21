from django.contrib import admin

from .models import (
    BookingItem,
    BookingPayment,
    BookingPaymentLink,
    BookingStatus,
    BookingUniqueIdSequence,
    FormTemplate,
    FormTemplateField,
    FormTemplateFieldOption,
)


class BookingPaymentInline(admin.TabularInline):
    model = BookingPayment
    extra = 0
    fields = [
        'payment_method',
        'amount',
        'tax',
        'transaction_status',
        'transaction_id',
        'transaction_date',
    ]
    readonly_fields = ['created_at']
    ordering = ['-transaction_date', '-created_at']


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
    list_display = [
        'unique_id',
        'title',
        'status',
        'total_amount',
        'total_tax',
        'created_by',
        'sort_order',
        'created_at',
    ]
    search_fields = ['unique_id', 'title']
    list_filter = ['status']
    ordering = ['sort_order', 'id']
    inlines = [BookingPaymentInline]


@admin.register(BookingPaymentLink)
class BookingPaymentLinkAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'booking',
        'status',
        'charge_amount',
        'base_amount',
        'public_token',
        'expires_at',
        'paid_at',
        'created_at',
    ]
    list_filter = ['status', 'company']
    search_fields = ['public_token', 'booking__unique_id', 'paymongo_checkout_session_id']
    readonly_fields = ['created_at', 'updated_at', 'public_token']
    raw_id_fields = ['booking', 'company', 'account', 'created_by']


@admin.register(BookingPayment)
class BookingPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'booking',
        'payment_method',
        'amount',
        'transaction_status',
        'transaction_date',
        'company',
        'created_at',
    ]
    list_filter = ['transaction_status', 'payment_method', 'company']
    search_fields = ['transaction_id', 'booking__unique_id', 'booking__title']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['booking', 'company', 'account']


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
