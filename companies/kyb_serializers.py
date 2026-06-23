from django.utils import timezone
from rest_framework import serializers

from .kyb import live_payments_allowed, missing_kyb_application_fields, provider_verification_payload
from .models import Company, CompanyKybVerification


class CompanyKybVerificationListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = CompanyKybVerification
        fields = [
            'id',
            'company',
            'company_name',
            'business_type',
            'paymongo_status',
            'xendit_status',
            'paymongo_merchant_id',
            'xendit_account_id',
            'merchant_business_name',
            'merchant_email',
            'merchant_mobile_number',
            'onboarding_url',
            'submitted_at',
            'xendit_submitted_at',
            'reviewed_at',
            'rejection_notes',
            'created_at',
            'updated_at',
        ]


class CompanyKybVerificationSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    live_payments_allowed = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()
    provider_verifications = serializers.SerializerMethodField()
    rejection_reason = serializers.CharField(
        source='rejection_notes',
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = CompanyKybVerification
        fields = [
            'id',
            'company',
            'company_name',
            'business_type',
            'paymongo_status',
            'paymongo_merchant_id',
            'onboarding_url',
            'xendit_status',
            'xendit_account_id',
            'xendit_onboarding_url',
            'xendit_rejection_notes',
            'merchant_business_name',
            'merchant_email',
            'merchant_mobile_number',
            'submitted_at',
            'reviewed_at',
            'reviewed_by',
            'rejection_notes',
            'rejection_reason',
            'live_payments_allowed',
            'missing_fields',
            'provider_verifications',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'company',
            'company_name',
            'paymongo_merchant_id',
            'onboarding_url',
            'xendit_status',
            'xendit_account_id',
            'xendit_onboarding_url',
            'xendit_rejection_notes',
            'submitted_at',
            'reviewed_at',
            'reviewed_by',
            'live_payments_allowed',
            'missing_fields',
            'provider_verifications',
            'created_at',
            'updated_at',
        ]

    def get_live_payments_allowed(self, obj) -> bool:
        return live_payments_allowed(obj)

    def get_provider_verifications(self, obj) -> dict:
        return provider_verification_payload(obj)

    def get_missing_fields(self, obj) -> list[str]:
        if obj.paymongo_status != CompanyKybVerification.PaymongoStatus.DRAFT:
            return []
        return missing_kyb_application_fields(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not (data.get('onboarding_url') or '').strip():
            from payments.models import PaymentIntegration

            integration = (
                PaymentIntegration.objects.filter(
                    company_id=instance.company_id,
                    payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
                    deleted_at__isnull=True,
                )
                .order_by('-id')
                .first()
            )
            if integration and (integration.identity_verification_url or '').strip():
                data['onboarding_url'] = integration.identity_verification_url
        data['provider_verifications'] = provider_verification_payload(instance)
        paymongo = dict(data['provider_verifications'].get('paymongo') or {})
        if (data.get('onboarding_url') or '').strip():
            paymongo['onboarding_url'] = data['onboarding_url']
            data['provider_verifications']['paymongo'] = paymongo
        return data

    def validate_business_type(self, value):
        value = (value or '').strip()
        if value and value not in CompanyKybVerification.BusinessType.values:
            raise serializers.ValidationError('Invalid business type.')
        return value

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None

        new_status = attrs.get('paymongo_status')
        if new_status is None and instance is not None:
            new_status = instance.paymongo_status

        if new_status in (
            CompanyKybVerification.PaymongoStatus.APPROVED,
            CompanyKybVerification.PaymongoStatus.REJECTED,
        ):
            from users.roles import has_feature_write

            if user is None or not has_feature_write(user, 'admin_company_verification'):
                raise serializers.ValidationError(
                    {'paymongo_status': ['Only administrators can approve or reject KYB.']},
                )

        if (
            new_status == CompanyKybVerification.PaymongoStatus.REJECTED
            and not (attrs.get('rejection_notes') or (instance and instance.rejection_notes))
        ):
            raise serializers.ValidationError(
                {'rejection_reason': ['Rejection reason is required when rejecting KYB.']},
            )

        for key in (
            'merchant_business_name',
            'merchant_email',
            'merchant_mobile_number',
            'rejection_notes',
        ):
            if key in attrs and attrs[key] is not None:
                attrs[key] = str(attrs[key]).strip()

        return attrs

    def update(self, instance, validated_data):
        new_status = validated_data.get('paymongo_status', instance.paymongo_status)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        now = timezone.now()

        if new_status in (
            CompanyKybVerification.PaymongoStatus.APPROVED,
            CompanyKybVerification.PaymongoStatus.REJECTED,
        ):
            validated_data.setdefault('reviewed_at', now)
            if user is not None and user.is_authenticated:
                validated_data.setdefault('reviewed_by', user)
        if new_status == CompanyKybVerification.PaymongoStatus.DRAFT:
            validated_data['reviewed_at'] = None
            validated_data['reviewed_by'] = None
            validated_data['rejection_notes'] = validated_data.get('rejection_notes', '')

        return super().update(instance, validated_data)
