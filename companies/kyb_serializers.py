from django.utils import timezone
from rest_framework import serializers

from .kyb import missing_kyb_fields
from .models import Company, CompanyKybVerification


class CompanyKybVerificationSerializer(serializers.ModelSerializer):
    live_payments_allowed = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()

    class Meta:
        model = CompanyKybVerification
        fields = [
            'id',
            'company',
            'business_type',
            'status',
            'government_id_file',
            'dti_registration_file',
            'sole_prop_business_address',
            'sole_prop_mobile_number',
            'bank_account_same_name',
            'sec_registration_file',
            'articles_of_incorporation_file',
            'bir_registration_file',
            'owner_director_id_files',
            'business_website_social',
            'company_email_domain',
            'proof_of_address_file',
            'business_description',
            'submitted_at',
            'reviewed_at',
            'reviewed_by',
            'rejection_notes',
            'live_payments_allowed',
            'missing_fields',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'company',
            'submitted_at',
            'reviewed_at',
            'reviewed_by',
            'live_payments_allowed',
            'missing_fields',
            'created_at',
            'updated_at',
        ]

    def get_live_payments_allowed(self, obj) -> bool:
        from .kyb import live_payments_allowed

        return live_payments_allowed(obj)

    def get_missing_fields(self, obj) -> list[str]:
        if obj.status != CompanyKybVerification.Status.DRAFT:
            return []
        return missing_kyb_fields(obj)

    def validate_business_type(self, value):
        value = (value or '').strip()
        if value and value not in CompanyKybVerification.BusinessType.values:
            raise serializers.ValidationError('Invalid business type.')
        return value

    def validate_owner_director_id_files(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('Must be a list of file references.')
        cleaned = []
        for item in value:
            if item in (None, ''):
                continue
            if isinstance(item, str):
                ref = item.strip()
                if ref:
                    cleaned.append(ref)
                continue
            if isinstance(item, dict):
                ref = str(item.get('file') or item.get('url') or '').strip()
                label = str(item.get('label') or '').strip()
                if ref:
                    cleaned.append({'label': label, 'file': ref})
                continue
            raise serializers.ValidationError(
                'Each entry must be a file path string or {label, file} object.',
            )
        return cleaned

    def _strip_text_fields(self, attrs):
        text_fields = (
            'sole_prop_business_address',
            'sole_prop_mobile_number',
            'bank_account_same_name',
            'business_website_social',
            'company_email_domain',
            'business_description',
            'rejection_notes',
        )
        file_fields = (
            'government_id_file',
            'dti_registration_file',
            'sec_registration_file',
            'articles_of_incorporation_file',
            'bir_registration_file',
            'proof_of_address_file',
        )
        for key in text_fields:
            if key in attrs:
                attrs[key] = (attrs[key] or '').strip()
        for key in file_fields:
            if key in attrs:
                attrs[key] = (attrs[key] or '').strip()
        return attrs

    def validate(self, attrs):
        attrs = self._strip_text_fields(attrs)
        instance = getattr(self, 'instance', None)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None

        new_status = attrs.get('status')
        if new_status is None and instance is not None:
            new_status = instance.status

        if new_status in (
            CompanyKybVerification.Status.APPROVED,
            CompanyKybVerification.Status.REJECTED,
        ):
            if user is None or not getattr(user, 'is_admin', False):
                raise serializers.ValidationError(
                    {'status': ['Only administrators can approve or reject KYB.']},
                )

        if new_status == CompanyKybVerification.Status.SUBMITTED:
            draft = instance or CompanyKybVerification()
            for key, val in attrs.items():
                setattr(draft, key, val)
            missing = missing_kyb_fields(draft)
            if missing:
                raise serializers.ValidationError(
                    {'detail': f'Missing required KYB fields: {", ".join(missing)}.'},
                )

        if (
            new_status == CompanyKybVerification.Status.REJECTED
            and not (attrs.get('rejection_notes') or (instance and instance.rejection_notes))
        ):
            raise serializers.ValidationError(
                {'rejection_notes': ['Rejection notes are required when rejecting KYB.']},
            )

        return attrs

    def update(self, instance, validated_data):
        new_status = validated_data.get('status', instance.status)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        now = timezone.now()

        if new_status == CompanyKybVerification.Status.SUBMITTED and not instance.submitted_at:
            validated_data['submitted_at'] = now
        if new_status in (
            CompanyKybVerification.Status.APPROVED,
            CompanyKybVerification.Status.REJECTED,
        ):
            validated_data.setdefault('reviewed_at', now)
            if user is not None and user.is_authenticated:
                validated_data.setdefault('reviewed_by', user)
        if new_status == CompanyKybVerification.Status.DRAFT:
            validated_data['reviewed_at'] = None
            validated_data['reviewed_by'] = None
            validated_data['rejection_notes'] = validated_data.get('rejection_notes', '')

        return super().update(instance, validated_data)
