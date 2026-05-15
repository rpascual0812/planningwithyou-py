from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import HasAccount

from .models import SupplierSettingTier, SupplierType, Tier
from .serializers import (
    SupplierOptionQuerySerializer,
    SupplierOptionSerializer,
    SupplierTypeSerializer,
    TierSerializer,
)


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


class TierViewSet(viewsets.ReadOnlyModelViewSet):
    """List active tiers for supplier form fields."""

    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = TierSerializer
    ordering = ['name']

    def get_queryset(self):
        return Tier.objects.filter(
            account_id=self.request.user.account_id,
            is_active=True,
        )


class SupplierOptionListView(APIView):
    """
    Suppliers (accounts) linked via active supplier_settings for the current
    account, filtered by tier through supplier_setting_tiers.
    """

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request):
        query = SupplierOptionQuerySerializer(
            data=request.query_params,
            context={'request': request},
        )
        query.is_valid(raise_exception=True)
        tier_id = query.validated_data['tier_id']
        account_id = request.user.account_id

        rows = (
            SupplierSettingTier.objects.filter(
                tier_id=tier_id,
                tier__account_id=account_id,
                tier__is_active=True,
                supplier_setting__account_id=account_id,
                supplier_setting__is_active=True,
                supplier_setting__supplier__is_active=True,
            )
            .select_related('supplier_setting__supplier')
            .order_by('supplier_setting__supplier__name', 'id')
        )
        serializer = SupplierOptionSerializer(rows, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
