from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'original_name', 'mime_type', 'size', 'uploaded_by', 'created_at')
    list_filter = ('mime_type',)
    search_fields = ('original_name',)
    readonly_fields = ('created_at',)
