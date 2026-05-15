from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import HasAccount

from .models import SupplierType
from .serializers import SupplierTypeSerializer


class SupplierTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """List/read global supplier types (active, not soft-deleted)."""

    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = SupplierTypeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        qs = SupplierType.objects.filter(is_active=True)
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs
