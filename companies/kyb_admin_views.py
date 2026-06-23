from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import FeatureAccess

from .kyb_serializers import (
    CompanyKybVerificationListSerializer,
    CompanyKybVerificationSerializer,
)
from .models import CompanyKybVerification


def _kyb_active_verification_filter() -> Q:
    """
    At least one provider has pending or approved verification.

    Excludes companies that have not started KYB on PayMongo or Xendit (both draft).
    """
    return Q(
        paymongo_status__in=[
            CompanyKybVerification.PaymongoStatus.PENDING_PAYMONGO,
            CompanyKybVerification.PaymongoStatus.APPROVED,
        ],
    ) | Q(
        xendit_status__in=[
            CompanyKybVerification.XenditStatus.PENDING,
            CompanyKybVerification.XenditStatus.APPROVED,
        ],
    )


class CompanyKybVerificationAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Admin list/review of KYB verifications across all companies."""

    feature_key = 'admin_company_verification'
    permission_classes = [IsAuthenticated, FeatureAccess]
    class Pagination(PageNumberPagination):
        page_size = 10

    pagination_class = Pagination

    def get_serializer_class(self):
        if self.action == 'list':
            return CompanyKybVerificationListSerializer
        return CompanyKybVerificationSerializer

    def get_queryset(self):
        qs = CompanyKybVerification.objects.select_related('company').filter(
            _kyb_active_verification_filter(),
        ).order_by(
            '-updated_at',
        )
        status = (
            self.request.query_params.get('status', '').strip()
            or self.request.query_params.get('paymongo_status', '').strip()
        )
        if status == CompanyKybVerification.PaymongoStatus.PENDING_PAYMONGO:
            qs = qs.filter(
                paymongo_status=CompanyKybVerification.PaymongoStatus.PENDING_PAYMONGO,
            )
        elif status == CompanyKybVerification.XenditStatus.PENDING:
            qs = qs.filter(
                xendit_status=CompanyKybVerification.XenditStatus.PENDING,
            )
        elif status == 'approved_paymongo':
            qs = qs.filter(
                paymongo_status=CompanyKybVerification.PaymongoStatus.APPROVED,
            )
        elif status == 'approved_xendit':
            qs = qs.filter(
                xendit_status=CompanyKybVerification.XenditStatus.APPROVED,
            )
        elif status == CompanyKybVerification.PaymongoStatus.APPROVED:
            qs = qs.filter(
                Q(paymongo_status=CompanyKybVerification.PaymongoStatus.APPROVED)
                | Q(xendit_status=CompanyKybVerification.XenditStatus.APPROVED),
            )
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(company__name__icontains=search)
                | Q(merchant_business_name__icontains=search)
                | Q(merchant_email__icontains=search),
            )
        return qs

    def partial_update(self, request, *args, **kwargs):
        """Allow admins to approve KYB (``paymongo_status=approved``)."""
        if 'paymongo_status' in request.data and request.data.get('paymongo_status') not in (
            CompanyKybVerification.PaymongoStatus.APPROVED,
        ):
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                {'paymongo_status': ['Only approval is supported from this endpoint.']},
            )
        return super().partial_update(request, *args, **kwargs)
