from rest_framework import serializers

from .models import SupportTicket, SupportTicketMessage
from .services import user_display_name


class SupportTicketMessageSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField(read_only=True)
    is_mine = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SupportTicketMessage
        fields = [
            'id',
            'body',
            'is_staff',
            'created_by',
            'created_by_name',
            'created_at',
            'is_mine',
        ]
        read_only_fields = fields

    def get_created_by_name(self, obj: SupportTicketMessage) -> str:
        return user_display_name(obj.created_by)

    def get_is_mine(self, obj: SupportTicketMessage) -> bool:
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return obj.created_by_id == request.user.pk


class SupportTicketMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(allow_blank=False)


class SupportTicketSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField(read_only=True)
    is_read = serializers.SerializerMethodField(read_only=True)
    can_delete = serializers.SerializerMethodField(read_only=True)
    message_count = serializers.SerializerMethodField(read_only=True)
    last_message_preview = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            'id',
            'title',
            'status',
            'created_by',
            'created_by_name',
            'created_at',
            'is_read',
            'can_delete',
            'message_count',
            'last_message_preview',
        ]
        read_only_fields = fields

    def get_created_by_name(self, obj: SupportTicket) -> str:
        return user_display_name(obj.created_by)

    def get_is_read(self, obj: SupportTicket) -> bool:
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return True
        reads = getattr(obj, '_prefetched_reads', None)
        if reads is not None:
            return any(r.user_id == request.user.pk for r in reads)
        return obj.reads.filter(user_id=request.user.pk).exists()

    def get_can_delete(self, obj: SupportTicket) -> bool:
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return obj.created_by_id == request.user.pk

    def get_message_count(self, obj: SupportTicket) -> int:
        count = getattr(obj, '_message_count', None)
        if count is not None:
            return count
        return obj.messages.count()

    def get_last_message_preview(self, obj: SupportTicket) -> str:
        last = getattr(obj, '_last_message', None)
        if last is None:
            last = obj.messages.order_by('-created_at', '-id').first()
        if last is None:
            return ''
        from django.utils.html import strip_tags

        text = strip_tags(last.body).strip()
        if len(text) > 120:
            return f'{text[:117]}...'
        return text


class SupportTicketDetailSerializer(SupportTicketSerializer):
    messages = SupportTicketMessageSerializer(many=True, read_only=True)

    class Meta(SupportTicketSerializer.Meta):
        fields = SupportTicketSerializer.Meta.fields + ['messages']


class SupportTicketCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    message = serializers.CharField(allow_blank=False)


class SupportTicketAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ['status']

    def validate_status(self, value):
        valid = {choice for choice, _ in SupportTicket.Status.choices}
        if value not in valid:
            raise serializers.ValidationError('Invalid status.')
        return value
