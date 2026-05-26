from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .payment_validity import valid_booking_payments_queryset
from .payout_report_serializers import BookingPaymentPayoutReportSerializer


class BookingPaymentPayoutReportViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Company-scoped payout report for Reports → Payouts."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'reports'
    serializer_class = BookingPaymentPayoutReportSerializer

    def get_queryset(self):
        user = self.request.user
        qs = (
            valid_booking_payments_queryset()
            .filter(
                account_id=user.account_id,
                company_id=user.company_id,
            )
            .select_related('booking')
            .order_by('-transaction_date', '-created_at')
        )

        payout = self.request.query_params.get('payout', '').strip().lower()
        if payout == 'pending':
            qs = qs.filter(payout_sent_at__isnull=True)
        elif payout == 'sent':
            qs = qs.filter(payout_sent_at__isnull=False)

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(booking__unique_id__icontains=search)
                | Q(booking__title__icontains=search)
                | Q(transaction_id__icontains=search),
            )
        return qs
