from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import IsAdmin

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

    permission_classes = [IsAuthenticated, IsAdmin]
    def get_serializer_class(self):
        if self.action == 'list':
            return CompanyKybVerificationListSerializer
        return CompanyKybVerificationSerializer

    def get_queryset(self):
        qs = CompanyKybVerification.objects.select_related('company').order_by(
            '-updated_at',
        )
        status = self.request.query_params.get('status', '').strip()
        if status in (
            CompanyKybVerification.Status.SUBMITTED,
            CompanyKybVerification.Status.APPROVED,
        ):
            qs = qs.filter(status=status)
        else:
            qs = qs.filter(
                status__in=[
                    CompanyKybVerification.Status.SUBMITTED,
                    CompanyKybVerification.Status.APPROVED,
                ],
            )
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(company__name__icontains=search)
                | Q(company_email_domain__icontains=search)
                | Q(business_description__icontains=search),
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
