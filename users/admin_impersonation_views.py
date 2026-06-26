from django.db.models import Q
from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import FeatureAccess

from .models import User
from .serializers import user_may_login


class AdminImpersonationUserSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True, default='')
    account_name = serializers.CharField(source='account.name', read_only=True, default='')
    can_impersonate = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'account',
            'account_name',
            'company',
            'company_name',
            'is_active',
            'can_impersonate',
        ]
        read_only_fields = fields

    def get_can_impersonate(self, obj) -> bool:
        return user_may_login(obj)


class AdminImpersonationUserViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """List tenant users for platform admin impersonation."""

    feature_key = 'platform_admin'
    permission_classes = [IsAuthenticated, FeatureAccess]
    serializer_class = AdminImpersonationUserSerializer

    def get_queryset(self):
        qs = (
            User.objects.filter(deleted_at__isnull=True)
            .select_related('account', 'company')
            .order_by('account_id', 'company_id', 'username')
        )
        raw_account = self.request.query_params.get('account_id', '').strip()
        if raw_account.isdigit():
            qs = qs.filter(account_id=int(raw_account))
        raw_company = self.request.query_params.get('company_id', '').strip()
        if raw_company.isdigit():
            qs = qs.filter(company_id=int(raw_company))
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return qs
