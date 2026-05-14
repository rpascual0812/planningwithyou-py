from django.contrib import admin

from .models import Document, DocumentFolder


@admin.register(DocumentFolder)
class DocumentFolderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_deleted', 'created_at', 'updated_at')
    list_filter = ('is_deleted',)
    search_fields = ('name',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'original_name', 'folder', 'mime_type', 'size', 'is_deleted', 'uploaded_by', 'created_at')
    list_filter = ('mime_type', 'is_deleted', 'folder')
    search_fields = ('original_name',)
    readonly_fields = ('created_at',)
