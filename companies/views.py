from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from rest_framework import filters, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from bookings.models import History

from planningwithyou.history.core import request_metadata
from planningwithyou.history.mixin import HistoryListMixin
from planningwithyou.history.record import (
    record_resource_create,
    record_resource_delete,
    record_resource_update,
)
from planningwithyou.history.serializers import HistorySerializer
from planningwithyou.history.snapshots import (
    COMPANY_FIELDS,
    diff_simple,
    diff_supplier_setting,
    snapshot_company,
    snapshot_supplier_setting,
)
from planningwithyou.permissions import HasAccount
from users.supplier_price import (
    build_supplier_setting_active_by_company,
    build_supplier_tiers_by_company,
    get_supplier_company_tier_pricing,
    save_supplier_company_tier_pricing,
)

from suppliers.models import SupplierSetting

from .kyb_serializers import CompanyKybVerificationSerializer
from .models import Company, CompanyKybVerification
from .serializers import CompanySerializer, SupplierCompanyTierPricingSerializer


class CompanyViewSet(HistoryListMixin, viewsets.ModelViewSet):
    """CRUD for tenant companies (soft-delete on destroy)."""

    history_resource_type = 'company'
    permission_classes = [IsAuthenticated, HasAccount]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    serializer_class = CompanySerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'name', 'sort_order', 'created_at']
    ordering = ['sort_order', 'name']

    def _is_supplier_directory(self) -> bool:
        """Supplier Settings: all companies (any account), not scoped to the current tenant."""
        return self.request.query_params.get('supplier_directory', '').lower() in (
            '1',
            'true',
            'yes',
        )

    def _uses_supplier_setting_active(self) -> bool:
        return self._is_supplier_directory() or bool(
            self.request.query_params.get('supplier_type', '').strip(),
        )

    def _annotate_supplier_setting_active(self, qs):
        if not self._uses_supplier_setting_active():
            return qs
        active_sq = SupplierSetting.objects.filter(
            supplier_id=OuterRef('pk'),
            account_id=self.request.user.account_id,
        ).values('is_active')[:1]
        return qs.annotate(_supplier_setting_is_active=Subquery(active_sq))

    def get_queryset(self):
        qs = Company.objects.filter(deleted_at__isnull=True).select_related(
            'supplier_type',
            'account__country',
        )

        if not self._is_supplier_directory():
            qs = qs.filter(account_id=self.request.user.account_id)

        supplier_type = self.request.query_params.get('supplier_type', '').strip()
        if supplier_type:
            qs = qs.filter(supplier_type_id=supplier_type)

        if self._uses_supplier_setting_active():
            qs = qs.filter(is_active=True)

        active_only = self.request.query_params.get('active_only', '').lower()
        if active_only in ('1', 'true', 'yes') and not self._uses_supplier_setting_active():
            qs = qs.filter(is_active=True)

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search)

        return self._annotate_supplier_setting_active(qs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        supplier_type = self.request.query_params.get('supplier_type', '').strip()
        if self._is_supplier_directory() or supplier_type:
            context['supplier_directory'] = True
        if self.action == 'list' and supplier_type:
            user = self.request.user
            qs = self.filter_queryset(self.get_queryset())
            company_ids = list(qs.values_list('id', flat=True))
            context['tier_pricing_by_supplier'] = build_supplier_tiers_by_company(
                company_ids,
                user.account_id,
            )
            context['supplier_setting_active_by_id'] = (
                build_supplier_setting_active_by_company(
                    company_ids,
                    user.account_id,
                )
            )
        return context

    def perform_create(self, serializer):
        from suppliers.models import SupplierType

        extra = {
            'account_id': self.request.user.account_id,
            'created_by': self.request.user,
        }
        if 'supplier_type' not in serializer.validated_data:
            default_type = SupplierType.objects.filter(is_active=True).order_by('id').first()
            if default_type is not None:
                extra['supplier_type'] = default_type
        company = serializer.save(**extra)
        record_resource_create(
            account_id=company.account_id,
            resource_type='company',
            resource_id=company.pk,
            snapshot=snapshot_company(company),
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )

    def perform_update(self, serializer):
        before = snapshot_company(serializer.instance)
        company = serializer.save()
        changes = diff_simple(before, snapshot_company(company), COMPANY_FIELDS)
        request = self.request

        def _record():
            record_resource_update(
                account_id=company.account_id,
                resource_type='company',
                resource_id=company.pk,
                changes=changes,
                actor=request.user,
                metadata=request_metadata(request),
            )

        transaction.on_commit(_record)

    def perform_destroy(self, instance):
        record_resource_delete(
            account_id=instance.account_id,
            resource_type='company',
            resource_id=instance.pk,
            changes={'name': instance.name},
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at'])

    @action(detail=True, methods=['get', 'patch'], url_path='tier-pricing')
    def tier_pricing(self, request, pk=None):
        company = self.get_object()
        tenant_account_id = request.user.account_id

        if request.method == 'GET':
            return Response(
                {
                    'name': company.name,
                    'tiers': get_supplier_company_tier_pricing(
                        company.id,
                        tenant_account_id,
                        supplier_account_id=company.account_id,
                    ),
                },
            )

        serializer = SupplierCompanyTierPricingSerializer(
            data=request.data,
            context={'request': request, 'supplier_company': company},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        before = snapshot_supplier_setting(company.id, tenant_account_id)
        if 'name' in data:
            name = data['name'].strip() or company.name
            if name != company.name:
                company.name = name
                company.save(update_fields=['name'])
        save_supplier_company_tier_pricing(
            company.id,
            tenant_account_id,
            data['tiers'],
            supplier_account_id=company.account_id,
        )
        after = snapshot_supplier_setting(company.id, tenant_account_id)
        changes = diff_supplier_setting(before, after)
        request = self.request

        def _record():
            record_resource_update(
                account_id=tenant_account_id,
                resource_type='supplier_setting',
                resource_id=company.id,
                changes=changes,
                actor=request.user,
                metadata=request_metadata(request),
            )

        transaction.on_commit(_record)
        return Response(
            {
                'name': company.name,
                'tiers': get_supplier_company_tier_pricing(
                    company.id,
                    tenant_account_id,
                    supplier_account_id=company.account_id,
                ),
            },
        )

    @action(detail=True, methods=['get'], url_path='supplier-setting/history')
    def supplier_setting_history(self, request, pk=None):
        company = self.get_object()
        tenant_account_id = request.user.account_id
        rows = (
            History.objects.filter(
                account_id=tenant_account_id,
                resource_type='supplier_setting',
                resource_id=company.pk,
            )
            .select_related('actor')
            .order_by('-created_at', '-id')
        )
        return Response(HistorySerializer(rows, many=True).data)

    def _get_or_create_kyb(self, company: Company) -> CompanyKybVerification:
        kyb, _created = CompanyKybVerification.objects.get_or_create(
            company=company,
        )
        return kyb

    @action(detail=True, methods=['get', 'patch', 'put'], url_path='kyb')
    def kyb(self, request, pk=None):
        """GET/PATCH Know Your Business verification for a company."""
        company = self.get_object()
        record = self._get_or_create_kyb(company)

        if request.method == 'GET':
            return Response(
                CompanyKybVerificationSerializer(
                    record,
                    context=self.get_serializer_context(),
                ).data,
            )

        serializer = CompanyKybVerificationSerializer(
            record,
            data=request.data,
            partial=request.method == 'PATCH',
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
