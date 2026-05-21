from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from planningwithyou.permissions import HasAccount, HasCompany

from .models import BookingPaymentLink
from .payment_link_serializers import BookingPaymentLinkSerializer
from .payment_links import PaymentLinkError, create_booking_payment_link, serialize_public_payment_link
from .paymongo_webhook import (
    handle_paymongo_webhook_event,
    normalize_paymongo_webhook_body,
    parse_webhook_body,
    verify_paymongo_signature,
)
from .scope import bookings_for_user


class BookingPaymentLinkListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany]

    def get(self, request, booking_id: int):
        booking = get_object_or_404(bookings_for_user(request.user), pk=booking_id)
        links = BookingPaymentLink.objects.filter(booking=booking).order_by('-created_at')
        return Response(BookingPaymentLinkSerializer(links, many=True).data)

    def post(self, request, booking_id: int):
        booking = get_object_or_404(bookings_for_user(request.user), pk=booking_id)
        try:
            link = create_booking_payment_link(booking, created_by=request.user)
        except PaymentLinkError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            BookingPaymentLinkSerializer(link).data,
            status=status.HTTP_201_CREATED,
        )


class BookingPaymentLinkDetailView(APIView):
    """Cancel a pending payment link (soft status change)."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany]

    def delete(self, request, booking_id: int, link_id: int):
        booking = get_object_or_404(bookings_for_user(request.user), pk=booking_id)
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
        signature = request.headers.get('Paymongo-Signature') or request.headers.get(
            'paymongo-signature',
        )
        if not verify_paymongo_signature(raw, signature):
            return Response({'detail': 'Invalid signature.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            body = parse_webhook_body(raw)
        except ValueError:
            return Response({'detail': 'Invalid JSON.'}, status=status.HTTP_400_BAD_REQUEST)

        handled = False
        for event in normalize_paymongo_webhook_body(body):
            if handle_paymongo_webhook_event(event):
                handled = True

        return Response({'received': True, 'handled': handled})
