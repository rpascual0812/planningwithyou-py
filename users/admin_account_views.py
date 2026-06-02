from django.db.models import Count, Q
from rest_framework import mixins, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import FeatureAccess

from .admin_account_serializers import AdminAccountListSerializer
from .models import Account


class AdminAccountViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Admin list of all tenant accounts with company and user counts."""

    feature_key = 'admin_accounts'
    permission_classes = [IsAuthenticated, FeatureAccess]
    serializer_class = AdminAccountListSerializer
    class Pagination(PageNumberPagination):
        page_size = 10

    pagination_class = Pagination

    def get_queryset(self):
        qs = (
            Account.objects.select_related('country')
            .annotate(
                company_count=Count(
                    'companies',
                    filter=Q(companies__deleted_at__isnull=True),
                    distinct=True,
                ),
                user_count=Count(
                    'users',
                    filter=Q(users__deleted_at__isnull=True),
                    distinct=True,
                ),
            )
            .order_by('-created_at')
        )
        search = self.request.query_params.get('search', '').strip()
        if not search:
            return qs
        filters = (
            Q(name__icontains=search)
            | Q(contact_email__icontains=search)
            | Q(contact_person__icontains=search)
        )
        if search.isdigit():
            filters |= Q(pk=int(search))
        return qs.filter(filters)
