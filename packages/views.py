from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from companies.models import Company
from planningwithyou.permissions import HasAccount, HasCompany

from .models import Package, PackageItem, PackageVersion
from .serializers import PackageSerializer, PackageVersionSerializer


class PackageViewSet(viewsets.ModelViewSet):
    """CRUD for packages (soft-delete on destroy)."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany]
    serializer_class = PackageSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'tier', 'total_price', 'created_at']
    ordering = ['tier_id', 'id']

    def get_queryset(self):
        account_id = self.request.user.account_id
        qs = Package.objects.filter(
            account_id=account_id,
            deleted_at__isnull=True,
        ).select_related('package_version', 'tier').prefetch_related(
            Prefetch(
                'items',
                queryset=PackageItem.objects.filter(
                    deleted_at__isnull=True,
                    parent__isnull=True,
                )
                .order_by('sort_order', 'id')
                .prefetch_related(
                    Prefetch(
                        'children',
                        queryset=PackageItem.objects.filter(deleted_at__isnull=True).order_by(
                            'sort_order',
                            'id',
                        ).prefetch_related(
                            Prefetch(
                                'children',
                                queryset=PackageItem.objects.filter(
                                    deleted_at__isnull=True,
                                ).order_by('sort_order', 'id'),
                            ),
                        ),
                    ),
                ),
            ),
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
        version_id = self.request.query_params.get('package_version_id', '').strip()
        if version_id:
            qs = qs.filter(package_version_id=version_id)
        tier_id = self.request.query_params.get('tier_id', '').strip()
        if tier_id:
            qs = qs.filter(tier_id=tier_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            account_id=self.request.user.account_id,
            created_by=self.request.user,
        )

    def perform_destroy(self, instance):
        was_active = instance.is_active
        scope = {
            'company_id': instance.company_id,
            'tier_id': instance.tier_id,
            'package_version_id': instance.package_version_id,
        }
        instance.deleted_at = timezone.now()
        instance.is_active = False
        instance.save(update_fields=['deleted_at', 'is_active'])
        if was_active:
            replacement = (
                Package.objects.filter(
                    deleted_at__isnull=True,
                    is_active=False,
                    **scope,
                )
                .order_by('id')
                .first()
            )
            if replacement is not None:
                Package.objects.filter(pk=replacement.pk).update(is_active=True)


class PackageVersionViewSet(viewsets.ModelViewSet):
    """CRUD for package versions (soft-delete on destroy)."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany]
    serializer_class = PackageVersionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'title', 'created_at']
    ordering = ['title', 'id']

    def get_queryset(self):
        account_id = self.request.user.account_id
        qs = PackageVersion.objects.filter(
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
