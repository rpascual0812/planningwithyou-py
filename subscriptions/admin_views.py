from decimal import Decimal

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import FeatureAccess

from .payment_provider import (
    PROVIDER_LABELS,
    VALID_PROVIDERS,
    provider_status_payload,
    set_subscription_payment_provider,
)
from .plan_pricing_settings import (
    plan_pricing_settings_payload,
    update_plan_pricing_settings,
)


class SubscriptionPaymentProviderSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=sorted(VALID_PROVIDERS))


class PlanPricingSerializer(serializers.Serializer):
    base_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    price_per_user = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
    )


class AdminPlanPricingSerializer(serializers.Serializer):
    base_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    price_per_user = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
    )


class SubscriptionPlanPricingSerializer(serializers.Serializer):
    pro = PlanPricingSerializer()
    ai = PlanPricingSerializer()
    admin = AdminPlanPricingSerializer()

class AdminSubscriptionPaymentProviderView(APIView):
    """Read or update the platform subscription billing payment provider."""

    feature_key = 'admin_subscriptions'
    permission_classes = [IsAuthenticated, FeatureAccess]

    def get(self, request):
        return Response(provider_status_payload())

    def patch(self, request):
        serializer = SubscriptionPaymentProviderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider = set_subscription_payment_provider(serializer.validated_data['provider'])
        payload = provider_status_payload()
        payload['provider'] = provider
        payload['provider_label'] = PROVIDER_LABELS.get(provider, provider.title())
        return Response(payload)


class SubscriptionPaymentProviderPublicView(APIView):
    """Active subscription payment provider for Account Settings → Subscription."""

    permission_classes = [IsAuthenticated, FeatureAccess]
    feature_key = 'account_settings'

    def get(self, request):
        return Response(provider_status_payload())


class AdminSubscriptionPlanPricingView(APIView):
    """Read or update Pro / AI Plus / Admin prices stored in the system table."""

    feature_key = 'admin_subscriptions'
    permission_classes = [IsAuthenticated, FeatureAccess]

    def get(self, request):
        return Response(plan_pricing_settings_payload())

    def patch(self, request):
        serializer = SubscriptionPlanPricingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            payload = update_plan_pricing_settings(
                pro_base_price=data['pro']['base_price'],
                pro_price_per_user=data['pro']['price_per_user'],
                ai_base_price=data['ai']['base_price'],
                ai_price_per_user=data['ai']['price_per_user'],
                admin_base_price=data['admin']['base_price'],
                admin_price_per_user=data['admin']['price_per_user'],
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(payload)