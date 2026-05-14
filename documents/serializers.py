from rest_framework import serializers

from .models import Document, DocumentFolder


class DocumentFolderSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = DocumentFolder
        fields = ['id', 'name', 'document_count', 'is_deleted', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_deleted', 'created_at', 'updated_at']

    def get_document_count(self, obj):
        return obj.documents.filter(is_deleted=False).count()


class DocumentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    is_image = serializers.BooleanField(read_only=True)
    extension = serializers.CharField(read_only=True)
    folder_name = serializers.CharField(source='folder.name', read_only=True, default='')

    class Meta:
        model = Document
        fields = [
            'id', 'file', 'original_name', 'mime_type', 'size',
            'extension', 'is_image', 'url', 'folder', 'folder_name',
            'uploaded_by', 'is_deleted', 'deleted_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'original_name', 'mime_type', 'size',
            'extension', 'is_image', 'url', 'uploaded_by',
            'is_deleted', 'deleted_at', 'created_at',
        ]

    def get_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else ''
