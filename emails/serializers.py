from django.core.validators import EmailValidator

from rest_framework import serializers

from .attachment_refs import (
    attachment_public_url,
    normalize_attachment_item,
)
from .mail import body_has_content
from .datetime_utils import company_timezone_name_for_email_log
from .models import EmailLog, EmailTemplate

_EMAIL_VALIDATOR = EmailValidator()


def normalize_email_address_list(value) -> list[str]:
    if value in (None, ''):
        return []
    if not isinstance(value, list):
        raise serializers.ValidationError('Must be a list of email addresses.')
    normalized: list[str] = []
    seen: set[str] = set()
    errors: list[str] = []
    for item in value:
        if item in (None, ''):
            continue
        addr = str(item).strip()
        if not addr:
            continue
        key = addr.lower()
        if key in seen:
            continue
        try:
            _EMAIL_VALIDATOR(addr)
        except Exception:
            errors.append(f'Invalid email address: {addr}')
            continue
        seen.add(key)
        normalized.append(addr)
    if errors:
        raise serializers.ValidationError(errors)
    return normalized


class EmailLogSerializer(serializers.ModelSerializer):
    company_timezone = serializers.SerializerMethodField()

    def get_company_timezone(self, obj) -> str:
        return company_timezone_name_for_email_log(obj)

    def validate_body(self, value):
        if not body_has_content(value):
            raise serializers.ValidationError('Message body is required.')
        return value

    def validate_attachments(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('Attachments must be a list.')
        normalized = []
        errors = []
        for item in value:
            if item in (None, ''):
                continue
            try:
                normalized.append(normalize_attachment_item(item))
            except ValueError as exc:
                errors.append(str(exc))
        if errors:
            raise serializers.ValidationError(errors)
        return normalized

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        data['attachments'] = [
            attachment_public_url(item, request=request)
            for item in (instance.attachments or [])
            if item not in (None, '')
        ]
        return data

    class Meta:
        model = EmailLog
        fields = [
            'id', 'to', 'cc', 'bcc', 'email_from', 'reply_to', 'subject',
            'body', 'attachments', 'created_by', 'company_id', 'company_timezone',
            'status', 'error', 'attempts', 'created_at', 'sent_at',
        ]
        read_only_fields = [
            'id', 'email_from', 'created_by', 'company_id',
            'status', 'error', 'attempts', 'created_at', 'sent_at',
        ]


class EmailTemplateSerializer(serializers.ModelSerializer):
    """Expose DB column ``type`` as ``type`` in the API (maps to ``template_type``)."""

    type = serializers.CharField(source='template_type', read_only=True)

    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'title', 'cc', 'bcc', 'subject', 'body', 'type',
            'is_active', 'is_default', 'company_id', 'created_at', 'updated_at',
            'deleted_at',
        ]
        read_only_fields = [
            'id', 'type', 'is_default', 'created_at', 'updated_at', 'deleted_at',
        ]

    def validate_cc(self, value):
        return normalize_email_address_list(value)

    def validate_bcc(self, value):
        return normalize_email_address_list(value)

    def validate_company_id(self, value):
        if value is None:
            return value
        request = self.context.get('request')
        if request is None:
            return value
        from companies.scope import company_belongs_to_account

        if not company_belongs_to_account(value, request.user.account_id):
            raise serializers.ValidationError('Company not found.')
        return value
