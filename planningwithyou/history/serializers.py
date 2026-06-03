from rest_framework import serializers

from bookings.models import History


class HistorySerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = History
        fields = [
            'id',
            'resource_type',
            'resource_id',
            'quotation_id',
            'entity_type',
            'entity_id',
            'action',
            'actor_id',
            'actor_name',
            'changes',
            'metadata',
            'created_at',
        ]
        read_only_fields = fields

    def get_actor_name(self, obj: History) -> str:
        user = obj.actor
        if user is None:
            return ''
        full = f'{user.first_name or ""} {user.last_name or ""}'.strip()
        return full or user.username or user.email or ''
