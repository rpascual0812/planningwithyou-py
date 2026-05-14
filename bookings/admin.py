from django.contrib import admin

from .models import FormTemplate, FormTemplateField, FormTemplateFieldOption


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
    list_display = ['name', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['name']
    inlines = [FormTemplateFieldInline]
