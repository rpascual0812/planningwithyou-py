from rest_framework import serializers

from .models import EmailLog, EmailTemplate


class EmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = [
            'id', 'to', 'cc', 'bcc', 'email_from', 'subject',
            'body_html', 'body_text', 'attachments',
            'status', 'error', 'attempts', 'created_at', 'sent_at',
        ]
        read_only_fields = ['id', 'status', 'error', 'attempts', 'created_at', 'sent_at']


class EmailTemplateSerializer(serializers.ModelSerializer):
    """Expose DB column ``type`` as ``type`` in the API (maps to ``template_type``)."""

    type = serializers.CharField(source='template_type', read_only=True)

    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'title', 'subject', 'body', 'type', 'is_active',
            'created_at', 'updated_at', 'deleted_at',
        ]
        read_only_fields = ['id', 'type', 'created_at', 'updated_at', 'deleted_at']
