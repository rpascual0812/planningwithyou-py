from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    is_image = serializers.BooleanField(read_only=True)
    extension = serializers.CharField(read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'file', 'original_name', 'mime_type', 'size',
            'extension', 'is_image', 'url', 'uploaded_by', 'created_at',
        ]
        read_only_fields = [
            'id', 'original_name', 'mime_type', 'size',
            'extension', 'is_image', 'url', 'uploaded_by', 'created_at',
        ]

    def get_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else ''
