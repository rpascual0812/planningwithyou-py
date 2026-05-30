import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .models import BookingPayment, BookingPaymentLink
from .payment_link_serializers import (
    BookingPaymentLinkSerializer,
    BookingPaymentSerializer,
)
from .payment_links import PaymentLinkError, create_booking_payment_link, serialize_public_payment_link
from .payment_summary import booking_payment_summary
from .paymongo_webhook import (
    company_id_from_webhook_body,
    parse_webhook_body,
    verify_paymongo_signature,
)
from payments.webhook_logging import (
    PAYMONGO_WEBHOOK_SOURCE,
    finalize_webhook_log,
    log_webhook,
)
from payments.webhook_processing import process_paymongo_webhook_body
from .scope import assert_booking_editable, bookings_for_user

logger = logging.getLogger(__name__)


class BookingPaymentLinkListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'bookings'

    def get(self, request, booking_id: int):
        booking = get_object_or_404(bookings_for_user(request.user), pk=booking_id)
        links = BookingPaymentLink.objects.filter(booking=booking).order_by('-created_at')
        payments = (
            BookingPayment.objects.filter(booking=booking, deleted_at__isnull=True)
            .order_by('-transaction_date', '-created_at')
        )
        return Response({
            'links': BookingPaymentLinkSerializer(links, many=True).data,
            'payments': BookingPaymentSerializer(payments, many=True).data,
            'summary': booking_payment_summary(booking),
        })

    def post(self, request, booking_id: int):
        booking = get_object_or_404(bookings_for_user(request.user), pk=booking_id)
        assert_booking_editable(booking, request.user)
        amount = request.data.get('amount')
        try:
            link = create_booking_payment_link(
                booking,
                charge_base_amount=amount,
                created_by=request.user,
            )
        except PaymentLinkError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            BookingPaymentLinkSerializer(link).data,
            status=status.HTTP_201_CREATED,
        )


class BookingPaymentLinkDetailView(APIView):
    """Cancel a pending payment link (soft status change)."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'bookings'

    def delete(self, request, booking_id: int, link_id: int):
        booking = get_object_or_404(bookings_for_user(request.user), pk=booking_id)
        assert_booking_editable(booking, request.user)
        link = get_object_or_404(BookingPaymentLink, pk=link_id, booking_id=booking.pk)
        if link.status == BookingPaymentLink.Status.PAID:
            return Response(
                {'detail': 'Paid payment links cannot be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        link.status = BookingPaymentLink.Status.CANCELLED
        link.save(update_fields=['status', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicPaymentLinkView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token: str):
        link = (
            BookingPaymentLink.objects.select_related(
                'booking',
                'booking__account',
                'booking__account__country',
                'company',
            )
            .filter(public_token=token)
            .first()
        )
        if link is None:
            return Response({'detail': 'Payment link not found.'}, status=status.HTTP_404_NOT_FOUND)
        if (
            link.status == BookingPaymentLink.Status.PENDING
            and link.expires_at < timezone.now()
        ):
            link.status = BookingPaymentLink.Status.EXPIRED
            link.save(update_fields=['status', 'updated_at'])
        return Response(serialize_public_payment_link(link))


@method_decorator(csrf_exempt, name='dispatch')
class PayMongoWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.body
        webhook_log = log_webhook(PAYMONGO_WEBHOOK_SOURCE, raw)

        if not raw:
            finalize_webhook_log(
                webhook_log,
                handled=False,
                error_message='Empty body',
            )
            logger.warning('PayMongo webhook rejected: empty request body')
            return Response({'detail': 'Empty body.'}, status=status.HTTP_400_BAD_REQUEST)

        signature = request.headers.get('Paymongo-Signature') or request.headers.get(
            'paymongo-signature',
        )
        try:
            body = parse_webhook_body(raw)
        except ValueError:
            finalize_webhook_log(
                webhook_log,
                handled=False,
                error_message='Invalid JSON',
            )
            logger.warning('PayMongo webhook rejected: invalid JSON body')
            return Response({'detail': 'Invalid JSON.'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(body, dict):
            finalize_webhook_log(
                webhook_log,
                handled=False,
                error_message='Invalid JSON envelope',
            )
            logger.warning('PayMongo webhook rejected: JSON root must be an object')
            return Response(
                {'detail': 'Invalid JSON envelope.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company_id = company_id_from_webhook_body(body)
        if not verify_paymongo_signature(raw, signature, company_id=company_id):
            finalize_webhook_log(
                webhook_log,
                handled=False,
                error_message='Invalid signature',
            )
            return Response({'detail': 'Invalid signature.'}, status=status.HTTP_400_BAD_REQUEST)

        handled = False
        try:
            handled = process_paymongo_webhook_body(body)
            finalize_webhook_log(webhook_log, handled=handled)
        except Exception as exc:
            logger.exception('PayMongo webhook processing failed (log_id=%s)', webhook_log.pk)
            finalize_webhook_log(
                webhook_log,
                handled=False,
                error_message=str(exc),
            )

        return Response({
            'received': True,
            'handled': handled,
            'webhook_log_id': webhook_log.pk,
        })
