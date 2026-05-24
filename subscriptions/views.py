from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.paymongo_client import PayMongoError
from planningwithyou.permissions import HasAccount
from users.models import Account

from .checkout import SubscriptionCheckoutError, start_subscription_checkout
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
        account_id = request.user.account_id
        today = timezone.localdate()
        row = (
            AccountSubscription.objects.filter(
                account_id=account_id,
                deleted_at__isnull=True,
            )
            .filter(
                Q(status=AccountSubscription.Status.PENDING)
                | (
                    Q(status=AccountSubscription.Status.ACTIVE)
                    & (Q(end_date__isnull=True) | Q(end_date__gte=today))
                ),
            )
            .select_related('subscription')
            .order_by('-status', '-start_date', '-id')
            .first()
        )
        if row is None:
            return Response(None)
        return Response(AccountSubscriptionSerializer(row).data)


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
