from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .payment_validity import payout_report_payments_queryset
from .payout_report_serializers import QuotationPaymentPayoutReportSerializer


class QuotationPaymentPayoutReportViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Company-scoped payout report for Reports → Payouts."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'reports'
    serializer_class = QuotationPaymentPayoutReportSerializer

    class Pagination(PageNumberPagination):
        page_size = 10

    pagination_class = Pagination

    def list(self, request, *args, **kwargs):
        paginated = (
            request.query_params.get('paginated', '').strip().lower() in ('1', 'true', 'yes')
            or request.query_params.get('page', '').strip() != ''
        )
        if not paginated:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        qs = (
            payout_report_payments_queryset()
            .filter(
                account_id=user.account_id,
                company_id=user.company_id,
            )
            .select_related('quotation')
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
                Q(quotation__unique_id__icontains=search)
                | Q(quotation__title__icontains=search)
                | Q(transaction_id__icontains=search),
            )
        return qs
