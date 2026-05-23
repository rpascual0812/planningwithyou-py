from rest_framework import serializers

from companies.models import Company

from .models import PaymentIntegration


def _mask_credential(value: str) -> str:
    trimmed = (value or '').strip()
    if not trimmed:
        return ''
    if len(trimmed) <= 8:
        return '••••••••'
    return f'{trimmed[:4]}…{trimmed[-4:]}'


class PayMongoIntegrationSerializer(serializers.Serializer):
    """Read/update PayMongo credentials for a company (secrets masked on read)."""

    payment_gateway = serializers.CharField(read_only=True, default='paymongo')
    uses_platform_defaults = serializers.BooleanField(read_only=True)
    has_custom_credentials = serializers.BooleanField(read_only=True)
    key_masked = serializers.CharField(read_only=True, allow_blank=True)
    webhook_secret_set = serializers.BooleanField(read_only=True)
    platform_configured = serializers.BooleanField(read_only=True)
    key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    secret = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def to_representation(self, instance):
        company: Company = self.context['company']
        integration = PaymentIntegration.objects.filter(
            company_id=company.pk,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
        ).first()
        from django.conf import settings

        platform_key = bool((getattr(settings, 'PAYMONGO_SECRET_KEY', None) or '').strip())
        has_custom = integration is not None and bool((integration.key or '').strip())
        uses_platform = not has_custom

        return {
            'payment_gateway': PaymentIntegration.PaymentGateway.PAYMONGO,
            'uses_platform_defaults': uses_platform,
            'has_custom_credentials': has_custom,
            'key_masked': _mask_credential(integration.key) if has_custom else '',
            'webhook_secret_set': bool(
                has_custom and (integration.secret or '').strip(),
            ),
            'platform_configured': platform_key,
        }

    def save(self, **kwargs):
        company: Company = self.context['company']
        user = self.context['request'].user
        key = (self.validated_data.get('key') or '').strip()
        secret = (self.validated_data.get('secret') or '').strip()

        if not key:
            raise serializers.ValidationError(
                {'key': ['PayMongo secret key is required.']},
            )

        integration = (
            PaymentIntegration.all_objects.filter(
                company_id=company.pk,
                payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
            )
            .order_by('-id')
            .first()
        )

        if integration is None:
            integration = PaymentIntegration(
                company=company,
                account_id=company.account_id,
                payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
                created_by=user,
            )
        else:
            integration.deleted_at = None
        integration.key = key
        if secret:
            integration.secret = secret
        elif not integration.pk:
            integration.secret = ''
        integration.save()
        if integration.created_by_id is None and user.is_authenticated:
            integration.created_by = user
            integration.save(update_fields=['created_by'])
        return integration
