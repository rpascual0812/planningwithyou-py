from django.utils import timezone
from rest_framework import serializers

from .kyb import missing_kyb_application_fields
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
            'status',
            'paymongo_merchant_id',
            'merchant_business_name',
            'merchant_email',
            'merchant_mobile_number',
            'onboarding_url',
            'submitted_at',
            'reviewed_at',
            'rejection_notes',
            'created_at',
            'updated_at',
        ]


class CompanyKybVerificationSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    live_payments_allowed = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()
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
            'status',
            'paymongo_merchant_id',
            'onboarding_url',
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
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'company',
            'company_name',
            'paymongo_merchant_id',
            'onboarding_url',
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

        new_status = attrs.get('status')
        if new_status is None and instance is not None:
            new_status = instance.status

        if new_status in (
            CompanyKybVerification.Status.APPROVED,
            CompanyKybVerification.Status.REJECTED,
        ):
            from users.roles import has_feature_write

            if user is None or not has_feature_write(user, 'admin_company_verification'):
                raise serializers.ValidationError(
                    {'status': ['Only administrators can approve or reject KYB.']},
                )

        if (
            new_status == CompanyKybVerification.Status.REJECTED
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
        new_status = validated_data.get('status', instance.status)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        now = timezone.now()

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
