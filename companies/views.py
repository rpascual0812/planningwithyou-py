from django.utils import timezone
from rest_framework import filters, parsers, viewsets
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import HasAccount

from .models import Company
from .serializers import CompanySerializer


class CompanyViewSet(viewsets.ModelViewSet):
    """CRUD for tenant companies (soft-delete on destroy)."""

    permission_classes = [IsAuthenticated, HasAccount]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    serializer_class = CompanySerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'name', 'sort_order', 'created_at']
    ordering = ['sort_order', 'name']

    def get_queryset(self):
        qs = Company.objects.filter(
            account_id=self.request.user.account_id,
            deleted_at__isnull=True,
        )
        active_only = self.request.query_params.get('active_only', '').lower()
        if active_only in ('1', 'true', 'yes'):
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            account_id=self.request.user.account_id,
            created_by=self.request.user,
        )

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at'])
