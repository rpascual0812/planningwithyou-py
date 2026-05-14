from django.contrib import admin

from .models import Contact, ContactAddress, ContactNumber


class ContactNumberInline(admin.TabularInline):
    model = ContactNumber
    extra = 1


class ContactAddressInline(admin.TabularInline):
    model = ContactAddress
    extra = 1


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'email', 'company', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'company')
    inlines = [ContactNumberInline, ContactAddressInline]
    readonly_fields = ('created_at', 'updated_at')
