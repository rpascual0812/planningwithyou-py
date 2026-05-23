from rest_framework import serializers

from companies.models import Company

from .models import PaymentIntegration


class PayMongoIntegrationSerializer(serializers.Serializer):
    """PayMongo Platforms linked child account status for a company."""

    payment_gateway = serializers.CharField(read_only=True, default='paymongo')
    platform_configured = serializers.BooleanField(read_only=True)
    platform_merchant_configured = serializers.BooleanField(read_only=True)
    paymongo_account_id = serializers.CharField(read_only=True, allow_blank=True)
    activation_status = serializers.CharField(read_only=True, allow_blank=True)
    identity_verification_status = serializers.CharField(read_only=True, allow_blank=True)
    identity_verification_url = serializers.URLField(read_only=True, allow_blank=True)
    payments_ready = serializers.BooleanField(read_only=True)
    onboarding_status_label = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        company: Company = self.context['company']
        integration = PaymentIntegration.objects.filter(
            company_id=company.pk,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
        ).first()
        from django.conf import settings

        from .paymongo_config import child_account_activated, get_platform_config

        platform = get_platform_config()
        platform_key = platform is not None
        platform_merchant = bool(
            (getattr(settings, 'PAYMONGO_PLATFORM_MERCHANT_ID', None) or '').strip(),
        )

        account_id = ''
        activation_status = 'not_started'
        identity_status = ''
        identity_url = ''
        if integration is not None:
            account_id = (integration.paymongo_account_id or '').strip()
            activation_status = integration.activation_status or 'pending'
            identity_status = integration.identity_verification_status or ''
            identity_url = integration.identity_verification_url or ''

        ready = child_account_activated(integration) and platform_merchant

        return {
            'payment_gateway': PaymentIntegration.PaymentGateway.PAYMONGO,
            'platform_configured': platform_key,
            'platform_merchant_configured': platform_merchant,
            'paymongo_account_id': account_id,
            'activation_status': activation_status,
            'identity_verification_status': identity_status,
            'identity_verification_url': identity_url,
            'payments_ready': ready,
            'onboarding_status_label': _onboarding_label(
                integration,
                platform_key=platform_key,
                platform_merchant=platform_merchant,
            ),
        }


def _onboarding_label(
    integration: PaymentIntegration | None,
    *,
    platform_key: bool,
    platform_merchant: bool,
) -> str:
    if not platform_key:
        return 'Platform not configured'
    if not platform_merchant:
        return 'Platform merchant id missing'
    if integration is None or not (integration.paymongo_account_id or '').strip():
        return 'Not connected'
    activation = (integration.activation_status or '').strip().lower()
    identity = (integration.identity_verification_status or '').strip().lower()
    if activation in {'activated', 'active'}:
        return 'Ready for payments'
    if identity in {'failed'}:
        return 'Identity verification failed'
    if identity not in {'passed', 'verified'}:
        return 'Complete PayMongo verification'
    if activation in {'declined'}:
        return 'Activation declined'
    return 'Pending activation'
