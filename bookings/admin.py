from django.contrib import admin

from .models import (
    Quotation,
    QuotationPayment,
    QuotationPaymentLink,
    QuotationStatus,
    QuotationUniqueIdSequence,
    FormTemplate,
    FormTemplateField,
    FormTemplateFieldOption,
)


class QuotationPaymentInline(admin.TabularInline):
    model = QuotationPayment
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


class QuotationInline(admin.TabularInline):
    model = Quotation
    extra = 0
    ordering = ['sort_order', 'id']


@admin.register(QuotationStatus)
class QuotationStatusAdmin(admin.ModelAdmin):
    list_display = ['title', 'color', 'sort_order', 'created_at']
    ordering = ['sort_order', 'id']
    inlines = [QuotationInline]


@admin.register(QuotationUniqueIdSequence)
class QuotationUniqueIdSequenceAdmin(admin.ModelAdmin):
    list_display = ['account_id', 'year', 'last_sequence']
    list_filter = ['year']


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = [
        'unique_id',
        'title',
        'status',
        'total_amount',
        'required_downpayment_amount',
        'created_by',
        'sort_order',
        'created_at',
    ]
    search_fields = ['unique_id', 'title']
    list_filter = ['status']
    ordering = ['sort_order', 'id']
    inlines = [QuotationPaymentInline]


@admin.register(QuotationPaymentLink)
class QuotationPaymentLinkAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'quotation',
        'status',
        'charge_amount',
        'base_amount',
        'public_token',
        'expires_at',
        'paid_at',
        'created_at',
    ]
    list_filter = ['status', 'company']
    search_fields = ['public_token', 'quotation__unique_id', 'paymongo_checkout_session_id']
    readonly_fields = ['created_at', 'updated_at', 'public_token']
    raw_id_fields = ['quotation', 'company', 'account', 'created_by']


@admin.register(QuotationPayment)
class QuotationPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'quotation',
        'payment_method',
        'base_amount',
        'charge_amount',
        'processing_fee',
        'platform_fee',
        'transaction_status',
        'transaction_date',
        'payout_sent_at',
        'company',
        'created_at',
    ]
    list_filter = ['transaction_status', 'payment_method', 'company', 'payout_sent_at']
    search_fields = ['transaction_id', 'quotation__unique_id', 'quotation__title']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['quotation', 'company', 'account']


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
