from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.paymongo_client import PayMongoError
from planningwithyou.permissions import FeatureAccess, HasAccount
from users.models import Account

from .account_plan import current_account_subscription
from .checkout import preview_subscription_checkout, start_subscription_checkout
from .errors import SubscriptionCheckoutError
from .free_plan import subscribe_account_to_free_plan
from .models import AccountSubscription, Subscription, SubscriptionReceipt
from .serializers import (
    AccountSubscriptionSerializer,
    SubscribeFreePlanSerializer,
    SubscriptionCheckoutSerializer,
    SubscriptionReceiptSerializer,
    SubscriptionSerializer,
)


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """Subscription plans for Settings → Subscription."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'
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

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'

    def get(self, request):
        row = current_account_subscription(request.user.account_id)
        if row is None:
            return Response(None)
        return Response(AccountSubscriptionSerializer(row).data)


class SubscriptionCheckoutPreviewView(APIView):
    """Quote amounts due now and on the next billing cycle before checkout."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'

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

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'

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


class SubscribeFreePlanView(APIView):
    """Activate Free immediately, or schedule Free at end of prepaid period when on a paid plan."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'

    def post(self, request):
        serializer = SubscribeFreePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        billing_cycle = serializer.validated_data.get(
            'billing_cycle',
            Subscription.BillingCycle.MONTHLY,
        )

        account = Account.objects.filter(pk=request.user.account_id).first()
        if account is None:
            return Response(
                {'detail': 'Account not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            row = subscribe_account_to_free_plan(
                account=account,
                billing_cycle=billing_cycle,
            )
        except SubscriptionCheckoutError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            AccountSubscriptionSerializer(row).data,
            status=status.HTTP_201_CREATED,
        )


class SubscriptionReceiptListView(APIView):
    """List subscription payment receipts for Account Settings → Receipts."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'

    def get(self, request):
        receipts = (
            SubscriptionReceipt.objects.filter(account_id=request.user.account_id)
            .select_related(
                'payment',
                'payment__account_subscription',
                'payment__account_subscription__subscription',
            )
            .order_by('-created_at')
        )
        return Response(SubscriptionReceiptSerializer(receipts, many=True).data)


class SubscriptionReceiptDownloadView(APIView):
    """Download a subscription receipt PDF."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'

    def get(self, request, receipt_id: int):
        receipt = (
            SubscriptionReceipt.objects.filter(
                pk=receipt_id,
                account_id=request.user.account_id,
            )
            .first()
        )
        if receipt is None:
            raise Http404
        key = (receipt.storage_key or '').strip()
        if key and default_storage.exists(key):
            handle = default_storage.open(key, 'rb')
            response = FileResponse(
                handle,
                content_type='application/pdf',
                as_attachment=True,
                filename=f'{receipt.receipt_number}.pdf',
            )
            return response
        if receipt.receipt_url:
            return Response({'receipt_url': receipt.receipt_url})
        raise Http404
