from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import HasAccount

from .models import SupplierSetting, SupplierSettingTier, SupplierType, Tier
from .serializers import (
    SupplierListOptionSerializer,
    SupplierOptionQuerySerializer,
    SupplierOptionSerializer,
    SupplierTierOptionSerializer,
    SupplierTierQuerySerializer,
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


class TierViewSet(viewsets.ModelViewSet):
    """CRUD for account tiers (soft-delete on destroy)."""

    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = TierSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        qs = Tier.objects.filter(
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


class SupplierOptionListView(APIView):
    """
  Suppliers linked to the current account via active supplier_settings.

  Without ``tier_id``: all suppliers for the account (pick supplier first).
  With ``tier_id``: suppliers that have that tier configured (legacy filter).
    """

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request):
        query = SupplierOptionQuerySerializer(
            data=request.query_params,
            context={'request': request},
        )
        query.is_valid(raise_exception=True)
        account_id = request.user.account_id
        tier_id = query.validated_data.get('tier_id')

        if tier_id is not None:
            rows = (
                SupplierSettingTier.objects.filter(
                    tier_id=tier_id,
                    tier__account_id=account_id,
                    tier__is_active=True,
                    tier__deleted_at__isnull=True,
                    supplier_setting__account_id=account_id,
                    supplier_setting__is_active=True,
                    supplier_setting__supplier__is_active=True,
                )
                .select_related('supplier_setting__supplier')
                .order_by('supplier_setting__supplier__name', 'id')
            )
            serializer = SupplierOptionSerializer(rows, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        settings = (
            SupplierSetting.objects.filter(
                account_id=account_id,
                is_active=True,
                supplier__is_active=True,
            )
            .select_related('supplier')
            .order_by('supplier__name', 'id')
        )
        serializer = SupplierListOptionSerializer(settings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SupplierTierListView(APIView):
    """Tiers configured for a supplier through supplier_setting_tiers."""

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request):
        query = SupplierTierQuerySerializer(
            data=request.query_params,
            context={'request': request},
        )
        query.is_valid(raise_exception=True)
        supplier_id = query.validated_data['supplier_id']
        account_id = request.user.account_id

        rows = (
            SupplierSettingTier.objects.filter(
                supplier_setting__account_id=account_id,
                supplier_setting__supplier_id=supplier_id,
                supplier_setting__is_active=True,
                tier__account_id=account_id,
                tier__is_active=True,
                tier__deleted_at__isnull=True,
            )
            .select_related('tier')
            .order_by('tier__name', 'id')
        )
        serializer = SupplierTierOptionSerializer(rows, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
