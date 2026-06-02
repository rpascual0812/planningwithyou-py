from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import FeatureAccess

from .models import BookingPayment
from .payment_validity import valid_booking_payments_queryset
from .payout_admin_serializers import (
    BookingPaymentPayoutAdminSerializer,
    BookingPaymentPayoutMarkSerializer,
)


class BookingPaymentPayoutAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Admin list of successful booking payments and payout-sent tracking."""

    feature_key = 'admin_payouts'
    permission_classes = [IsAuthenticated, FeatureAccess]
    serializer_class = BookingPaymentPayoutAdminSerializer
    class Pagination(PageNumberPagination):
        page_size = 10

    pagination_class = Pagination

    def get_queryset(self):
        qs = (
            valid_booking_payments_queryset()
            .select_related('company', 'booking')
            .order_by('-transaction_date', '-created_at')
        )
        company_id = self.request.query_params.get('company_id', '').strip()
        if company_id.isdigit():
            qs = qs.filter(company_id=int(company_id))

        payout = self.request.query_params.get('payout', '').strip().lower()
        if payout == 'pending':
            qs = qs.filter(payout_sent_at__isnull=True)
        elif payout == 'sent':
            qs = qs.filter(payout_sent_at__isnull=False)

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(company__name__icontains=search)
                | Q(booking__unique_id__icontains=search)
                | Q(booking__title__icontains=search)
                | Q(transaction_id__icontains=search),
            )
        return qs

    @action(detail=True, methods=['post'], url_path='mark-payout-sent')
    def mark_payout_sent(self, request, pk=None):
        payment = self.get_object()
        serializer = BookingPaymentPayoutMarkSerializer(
            data={'payout_sent': True},
            context={'payment': payment},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            BookingPaymentPayoutAdminSerializer(payment).data,
            status=status.HTTP_200_OK,
        )
