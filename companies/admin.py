from django.contrib import admin

from .models import Company, CompanyKybVerification


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'account',
        'is_active',
        'is_main',
        'kyb_verified',
        'sort_order',
        'created_at',
    )
    list_filter = ('is_active', 'is_main', 'kyb_verified', 'account')
    search_fields = ('name', 'website', 'contact_person', 'phone_number', 'mobile_number')
    readonly_fields = ('created_at',)
    raw_id_fields = ('account', 'created_by')


@admin.register(CompanyKybVerification)
class CompanyKybVerificationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'company',
        'business_type',
        'status',
        'submitted_at',
        'reviewed_at',
        'updated_at',
    )
    list_filter = ('status', 'business_type')
    search_fields = ('company__name', 'company_email_domain', 'business_description')
    readonly_fields = ('created_at', 'updated_at', 'submitted_at', 'reviewed_at')
    raw_id_fields = ('company', 'reviewed_by')
