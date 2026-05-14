from rest_framework import serializers

from .models import EmailLog


class EmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = [
            'id', 'to', 'cc', 'bcc', 'email_from', 'subject',
            'body_html', 'body_text', 'attachments',
            'status', 'error', 'attempts', 'created_at', 'sent_at',
        ]
        read_only_fields = ['id', 'status', 'error', 'attempts', 'created_at', 'sent_at']
