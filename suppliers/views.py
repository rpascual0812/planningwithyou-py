from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company

from planningwithyou.permissions import FeatureAccess, HasAccount

from .models import SupplierType, Tier
from .serializers import (
    SupplierOptionQuerySerializer,
    SupplierTierQuerySerializer,
    SupplierTypeSerializer,
    TierSerializer,
)


class PublicSupplierTypeListView(APIView):
    """Active supplier types for registration (no authentication)."""

    permission_classes = [AllowAny]

    def get(self, request):
        qs = SupplierType.objects.filter(is_active=True).order_by('name')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        serializer = SupplierTypeSerializer(qs, many=True)
        return Response(serializer.data)


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

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'supplier_settings'
    serializer_class = TierSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        account_id = self.request.user.account_id
        qs = Tier.objects.filter(
            account_id=account_id,
            deleted_at__isnull=True,
        )
        company_id = self.request.query_params.get('company_id', '').strip()
        if company_id:
            if not Company.objects.filter(
                pk=company_id,
                account_id=account_id,
                deleted_at__isnull=True,
            ).exists():
                return qs.none()
            qs = qs.filter(company_id=company_id)
        else:
            qs = qs.filter(company_id=self.request.user.company_id)
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
    Companies for the booking supplier field: ``supplier_settings.is_active``,
    optionally filtered by ``supplier_type``.
    """

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'bookings'

    def get(self, request):
        query = SupplierOptionQuerySerializer(
            data=request.query_params,
            context={'request': request},
        )
        query.is_valid(raise_exception=True)
        data = query.validated_data

        from users.supplier_price import get_booking_supplier_options

        supplier_type_id = data.get('supplier_type')
        include_supplier_id = data.get('supplier_id')

        return Response(
            get_booking_supplier_options(
                request.user.account_id,
                supplier_type_id=supplier_type_id,
                include_supplier_id=include_supplier_id,
            ),
            status=status.HTTP_200_OK,
        )


class SupplierTierListView(APIView):
    """Tiers configured for a supplier through supplier_setting_tiers."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'bookings'

    def get(self, request):
        query = SupplierTierQuerySerializer(
            data=request.query_params,
            context={'request': request},
        )
        query.is_valid(raise_exception=True)
        supplier_company_id = query.validated_data['supplier_id']

        from users.supplier_price import get_supplier_company_tier_options

        return Response(
            get_supplier_company_tier_options(
                supplier_company_id,
                request.user.account_id,
                request.user.company_id,
            ),
            status=status.HTTP_200_OK,
        )
