from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.paymongo_client import PayMongoError
from planningwithyou.permissions import HasAccount
from users.models import Account

from .account_plan import current_account_subscription
from .checkout import (
    SubscriptionCheckoutError,
    preview_subscription_checkout,
    start_subscription_checkout,
)
from .models import AccountSubscription, Subscription
from .serializers import (
    AccountSubscriptionSerializer,
    SubscriptionCheckoutSerializer,
    SubscriptionSerializer,
)


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """Subscription plans for Settings → Subscription."""

    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = SubscriptionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['sort_order', 'plan', 'base_price']
    ordering = ['sort_order', 'plan']

    def get_queryset(self):
        qs = Subscription.objects.filter(is_active=True)
        billing_cycle = self.request.query_params.get('billing_cycle', '').strip()
        if billing_cycle in Subscription.BillingCycle.values:
            qs = qs.filter(billing_cycle=billing_cycle)
        return qs


class AccountSubscriptionCurrentView(APIView):
    """Active or pending account subscription for Settings → Subscription."""

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request):
        row = current_account_subscription(request.user.account_id)
        if row is None:
            return Response(None)
        return Response(AccountSubscriptionSerializer(row).data)


class SubscriptionCheckoutPreviewView(APIView):
    """Quote amounts due now and on the next billing cycle before checkout."""

    permission_classes = [IsAuthenticated, HasAccount]

    def post(self, request):
        serializer = SubscriptionCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        subscription = Subscription.objects.filter(
            plan=data['plan'],
            billing_cycle=data['billing_cycle'],
            is_active=True,
            is_selectable=True,
        ).first()
        if subscription is None:
            return Response(
                {'detail': 'Subscription plan not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        account = Account.objects.filter(pk=request.user.account_id).first()
        if account is None:
            return Response(
                {'detail': 'Account not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payload = preview_subscription_checkout(
                account=account,
                subscription=subscription,
                team_seats=data.get('team_seats') or 1,
            )
        except SubscriptionCheckoutError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(payload)


class SubscriptionCheckoutView(APIView):
    """Start PayMongo subscription checkout; returns redirect URL."""

    permission_classes = [IsAuthenticated, HasAccount]

    def post(self, request):
        serializer = SubscriptionCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        subscription = Subscription.objects.filter(
            plan=data['plan'],
            billing_cycle=data['billing_cycle'],
            is_active=True,
            is_selectable=True,
        ).first()
        if subscription is None:
            return Response(
                {'detail': 'Subscription plan not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        account = Account.objects.filter(pk=request.user.account_id).first()
        if account is None:
            return Response(
                {'detail': 'Account not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = start_subscription_checkout(
                account=account,
                user=request.user,
                subscription=subscription,
                team_seats=data.get('team_seats') or 1,
                discount_code=data.get('discount_code') or '',
            )
        except SubscriptionCheckoutError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PayMongoError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(result, status=status.HTTP_201_CREATED)
