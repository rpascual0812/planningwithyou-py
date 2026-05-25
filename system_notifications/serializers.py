from rest_framework import serializers

from .models import SystemNotification


class SystemNotificationSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SystemNotification
        fields = [
            'id',
            'title',
            'message',
            'start_date',
            'end_date',
            'created_by',
            'created_by_name',
            'created_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at']

    def get_created_by_name(self, obj: SystemNotification) -> str:
        user = obj.created_by
        if user is None:
            return ''
        full = f'{user.first_name or ""} {user.last_name or ""}'.strip()
        return full or user.username or user.email or ''

    def validate(self, attrs):
        start = attrs.get('start_date')
        end = attrs.get('end_date')
        if self.instance is not None:
            start = start if start is not None else self.instance.start_date
            end = end if end is not None else self.instance.end_date
        if start and end and end < start:
            raise serializers.ValidationError(
                {'end_date': ['End date must be on or after the start date.']},
            )
        return attrs


class SystemNotificationPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemNotification
        fields = ['id', 'title', 'message', 'start_date', 'end_date']
