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
        status = self.request.query_params.get('status', '').strip()
        if status in CompanyKybVerification.Status.values:
            qs = qs.filter(status=status)
        else:
            qs = qs.filter(
                status__in=[
                    CompanyKybVerification.Status.PENDING_PAYMONGO,
                    CompanyKybVerification.Status.APPROVED,
                    CompanyKybVerification.Status.REJECTED,
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
        """Allow admins to approve KYB (``status=approved``)."""
        if 'status' in request.data and request.data.get('status') not in (
            CompanyKybVerification.Status.APPROVED,
        ):
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                {'status': ['Only approval is supported from this endpoint.']},
            )
        return super().partial_update(request, *args, **kwargs)
