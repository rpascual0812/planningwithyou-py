from rest_framework import serializers

from .models import ErrorLog


class ErrorLogAdminListSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    account_name = serializers.SerializerMethodField()
    is_resolved = serializers.SerializerMethodField()

    class Meta:
        model = ErrorLog
        fields = (
            'id',
            'method',
            'path',
            'query_string',
            'status_code',
            'exception_type',
            'exception_message',
            'user',
            'user_email',
            'account',
            'account_name',
            'ip_address',
            'created_at',
            'resolved_at',
            'is_resolved',
        )
        read_only_fields = fields

    def get_user_email(self, obj) -> str | None:
        if obj.user_id is None:
            return None
        return obj.user.email or None

    def get_account_name(self, obj) -> str | None:
        if obj.account_id is None:
            return None
        return obj.account.name or None

    def get_is_resolved(self, obj) -> bool:
        return obj.resolved_at is not None


class ErrorLogAdminDetailSerializer(ErrorLogAdminListSerializer):
    class Meta(ErrorLogAdminListSerializer.Meta):
        fields = ErrorLogAdminListSerializer.Meta.fields + (
            'traceback',
            'request_body',
            'user_agent',
        )
        read_only_fields = fields
