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
        qs = CompanyKybVerification.objects.select_related('company').order_by(
            '-updated_at',
        )
        paymongo_status = self.request.query_params.get('paymongo_status', '').strip()
        if paymongo_status in CompanyKybVerification.PaymongoStatus.values:
            qs = qs.filter(paymongo_status=paymongo_status)
        else:
            qs = qs.filter(
                paymongo_status__in=[
                    CompanyKybVerification.PaymongoStatus.PENDING_PAYMONGO,
                    CompanyKybVerification.PaymongoStatus.APPROVED,
                    CompanyKybVerification.PaymongoStatus.REJECTED,
                ],
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
