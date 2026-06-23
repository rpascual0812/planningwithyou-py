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
from .lifecycle import resolve_account_subscription_for_account
from .checkout import preview_subscription_checkout, start_subscription_checkout
from .errors import SubscriptionCheckoutError
from .free_plan import subscribe_account_to_free_plan
from .lifecycle import get_account_subscription_row
from .models import AccountSubscription, Subscription, SubscriptionPayment, SubscriptionReceipt
from .plans import ADMIN_PLAN, user_may_view_plan
from .serializers import (
    AccountSubscriptionSerializer,
    SubscribeFreePlanSerializer,
    SubscriptionCheckoutSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionReceiptSerializer,
    SubscriptionSerializer,
)
from .payment_provider import PROVIDER_LABELS, active_subscription_payment_provider
from .plan_pricing_settings import sync_subscription_plan_prices_from_system
from .subscription_billing_notifications import issue_subscription_payment_receipt
from .xendit_activation import apply_xendit_payment_session_completed
from .xendit_client import XenditError, retrieve_session


def _xendit_error_response(exc: XenditError) -> Response:
    body: dict = {'detail': str(exc)}
    if isinstance(exc.payload, dict):
        errors = exc.payload.get('errors')
        if errors:
            body['errors'] = errors
    return Response(body, status=status.HTTP_502_BAD_GATEWAY)


def _receipt_download_response(receipt: SubscriptionReceipt):
    key = (receipt.storage_key or '').strip()
    if key and default_storage.exists(key):
        handle = default_storage.open(key, 'rb')
        return FileResponse(
            handle,
            content_type='application/pdf',
            as_attachment=True,
            filename=f'{receipt.receipt_number}.pdf',
        )
    if receipt.receipt_url:
        return Response({'receipt_url': receipt.receipt_url})
    raise Http404


def _subscription_plans_queryset(user):
    sync_subscription_plan_prices_from_system()
    qs = Subscription.objects.filter(is_active=True)
    if not user_may_view_plan(user, ADMIN_PLAN):
        qs = qs.exclude(plan=ADMIN_PLAN)
    return qs


def _checkout_subscription(user, *, plan: str, billing_cycle: str) -> Subscription | None:
    subscription = Subscription.objects.filter(
        plan=plan,
        billing_cycle=billing_cycle,
        is_active=True,
        is_selectable=True,
    ).first()
    if subscription is None or not user_may_view_plan(user, subscription.plan):
        return None
    return subscription


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """Subscription plans for Settings → Subscription."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'
    serializer_class = SubscriptionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['sort_order', 'plan', 'base_price']
    ordering = ['sort_order', 'plan']

    def get_queryset(self):
        qs = _subscription_plans_queryset(self.request.user)
        billing_cycle = self.request.query_params.get('billing_cycle', '').strip()
        if billing_cycle in Subscription.BillingCycle.values:
            qs = qs.filter(billing_cycle=billing_cycle)
        return qs


class AccountSubscriptionCurrentView(APIView):
    """Active or pending account subscription for Settings → Subscription."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'

    def get(self, request):
        row, _expired = resolve_account_subscription_for_account(request.user.account_id)
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

        subscription = _checkout_subscription(
            request.user,
            plan=data['plan'],
            billing_cycle=data['billing_cycle'],
        )
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
                renew_expired=bool(data.get('renew_expired')),
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

        subscription = _checkout_subscription(
            request.user,
            plan=data['plan'],
            billing_cycle=data['billing_cycle'],
        )
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
                renew_expired=bool(data.get('renew_expired')),
            )
        except SubscriptionCheckoutError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PayMongoError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except XenditError as exc:
            return _xendit_error_response(exc)

        return Response(result, status=status.HTTP_201_CREATED)


class SubscriptionCheckoutConfirmView(APIView):
    """Confirm a pending Xendit checkout after the customer returns from payment."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'

    @staticmethod
    def _confirm_payload(**extra):
        provider = active_subscription_payment_provider()
        return {
            'provider': provider,
            'provider_label': PROVIDER_LABELS.get(provider, provider.title()),
            **extra,
        }

    def post(self, request):
        provider = active_subscription_payment_provider()
        if provider != 'xendit':
            return Response(self._confirm_payload(activated=False, subscription=None))

        account_sub = get_account_subscription_row(request.user.account_id)
        if account_sub is None:
            return Response(self._confirm_payload(activated=False, subscription=None))

        if account_sub.status == AccountSubscription.Status.ACTIVE:
            row = current_account_subscription(request.user.account_id)
            return Response(
                self._confirm_payload(
                    activated=True,
                    subscription=AccountSubscriptionSerializer(row).data if row else None,
                ),
            )

        session_id = (account_sub.reference_id or '').strip()
        if not session_id:
            return Response(
                {'detail': 'No pending checkout session was found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = retrieve_session(session_id)
        except XenditError as exc:
            return _xendit_error_response(exc)

        session_status = str(session.get('status') or '').strip().upper()
        account_sub_data = AccountSubscriptionSerializer(account_sub).data

        if session_status == 'COMPLETED':
            handled = apply_xendit_payment_session_completed(session)
            row = current_account_subscription(request.user.account_id)
            return Response(
                self._confirm_payload(
                    activated=handled,
                    subscription=AccountSubscriptionSerializer(row).data if row else None,
                ),
            )

        if session_status in {'EXPIRED', 'CANCELED'}:
            apply_xendit_payment_session_failed(session)
            return Response(
                self._confirm_payload(
                    activated=False,
                    payment_failed=True,
                    session_status=session_status.lower(),
                    subscription=account_sub_data,
                ),
            )

        return Response(
            self._confirm_payload(
                activated=False,
                pending=True,
                payment_failed=False,
                subscription=account_sub_data,
            ),
        )


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


class SubscriptionPaymentListView(APIView):
    """List subscription payments for Account Settings → Receipts."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'

    def get(self, request):
        payments = (
            SubscriptionPayment.objects.filter(account_id=request.user.account_id)
            .select_related(
                'receipt',
                'account_subscription',
                'account_subscription__subscription',
            )
            .order_by('-paid_at', '-id')
        )
        return Response(SubscriptionPaymentSerializer(payments, many=True).data)


class SubscriptionPaymentReceiptDownloadView(APIView):
    """Ensure and download the PDF receipt for a subscription payment."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'account_settings'

    def get(self, request, payment_id: int):
        payment = (
            SubscriptionPayment.objects.filter(
                pk=payment_id,
                account_id=request.user.account_id,
            )
            .first()
        )
        if payment is None:
            raise Http404
        receipt = issue_subscription_payment_receipt(payment.pk)
        if receipt is None:
            return Response(
                {'detail': 'Receipt is not available for this payment.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return _receipt_download_response(receipt)


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
        return _receipt_download_response(receipt)
