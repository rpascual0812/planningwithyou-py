from rest_framework import serializers

from .models import UserNotification


class UserNotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = UserNotification
        fields = [
            'id',
            'category',
            'severity',
            'title',
            'message',
            'action_url',
            'company_id',
            'is_read',
            'read_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_is_read(self, obj) -> bool:
        return obj.read_at is not None
