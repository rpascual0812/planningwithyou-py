from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from planningwithyou.template_placeholders import (
    DEFAULT_PASSWORD_RESET_BODY_HTML,
    DEFAULT_PASSWORD_RESET_SUBJECT,
    EMAIL_TEMPLATE_PASSWORD_RESET,
    apply_template_placeholders,
)

from emails.mail import create_and_queue_email
from emails.models import EmailTemplate
from emails.tasks import send_email_task

from .models import Account, PasswordResetToken
from .supplier_price import supplier_accounts_with_price_queryset
from .serializers import (
    AccountSerializer,
    EmailTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    SupplierAccountTierPricingSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from .supplier_price import (
    build_supplier_tiers_by_account,
    get_supplier_account_tier_pricing,
    save_supplier_account_tier_pricing,
)

User = get_user_model()


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


def _send_reset_email(user):
    PasswordResetToken.objects.filter(user=user, used=False).update(used=True)
    reset = PasswordResetToken.objects.create(user=user)
    name = (
        f'{user.first_name} {user.last_name}'.strip()
        or user.username
    )
    reset_url = f'{settings.FRONTEND_URL}/reset-password/{reset.token}'
    lifetime = settings.PASSWORD_RESET_TOKEN_LIFETIME_HOURS
    context = {
        'name': name,
        'reset_url': reset_url,
        'lifetime': str(lifetime),
    }

    tmpl = (
        EmailTemplate.objects.filter(
            name=EMAIL_TEMPLATE_PASSWORD_RESET,
            account_id=user.account_id,
            template_type=EmailTemplate.TemplateType.USERS,
            is_active=True,
            deleted_at__isnull=True,
        )
        .order_by('id')
        .first()
    )
    if tmpl and (tmpl.subject.strip() or tmpl.body.strip()):
        subject = apply_template_placeholders(
            tmpl.subject.strip() or DEFAULT_PASSWORD_RESET_SUBJECT,
            context,
        )
        body = apply_template_placeholders(tmpl.body, context)
        if not body.strip():
            body = apply_template_placeholders(
                DEFAULT_PASSWORD_RESET_BODY_HTML,
                context,
            )
    else:
        subject = apply_template_placeholders(
            DEFAULT_PASSWORD_RESET_SUBJECT,
            context,
        )
        body = apply_template_placeholders(
            DEFAULT_PASSWORD_RESET_BODY_HTML,
            context,
        )

    log = create_and_queue_email(
        to=[user.email],
        subject=subject,
        body=body,
        account=getattr(user, 'account', None),
    )
    send_email_task.delay(log.pk)


class AccountViewSet(viewsets.ModelViewSet):
    """Accounts (tenant organizations), filterable by supplier type."""

    permission_classes = [IsAuthenticated]
    serializer_class = AccountSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'name', 'status', 'created_at', 'updated_at']
    ordering = ['name']

    def get_queryset(self):
        qs = Account.objects.select_related('supplier_type', 'country')
        supplier_type = self.request.query_params.get('supplier_type', '').strip()
        if supplier_type:
            qs = qs.filter(supplier_type_id=supplier_type)
            tenant_account_id = getattr(self.request.user, 'account_id', None)
            if tenant_account_id:
                qs = supplier_accounts_with_price_queryset(qs, tenant_account_id)
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(status__icontains=search),
            )
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        supplier_type = self.request.query_params.get('supplier_type', '').strip()
        if self.action == 'list' and supplier_type:
            tenant_account_id = getattr(self.request.user, 'account_id', None)
            if tenant_account_id:
                qs = self.filter_queryset(self.get_queryset())
                supplier_ids = list(qs.values_list('id', flat=True))
                context['tier_pricing_by_supplier'] = build_supplier_tiers_by_account(
                    supplier_ids,
                    tenant_account_id,
                )
        return context

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at', 'updated_at'])

    @action(detail=False, methods=['get'], url_path='current')
    def current(self, request):
        account_id = getattr(request.user, 'account_id', None)
        if not account_id:
            return Response(
                {'detail': 'No account associated with this user.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        account = (
            Account.objects.select_related('country', 'supplier_type')
            .filter(pk=account_id, deleted_at__isnull=True)
            .first()
        )
        if account is None:
            return Response(
                {'detail': 'Account not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = AccountSerializer(account)
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'patch'], url_path='tier-pricing')
    def tier_pricing(self, request, pk=None):
        account = self.get_object()
        tenant_account_id = getattr(request.user, 'account_id', None)
        if not tenant_account_id:
            return Response(
                {'detail': 'No account associated with this user.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.method == 'GET':
            return Response(
                {
                    'name': account.name,
                    'tiers': get_supplier_account_tier_pricing(
                        account.id,
                        tenant_account_id,
                    ),
                },
            )

        serializer = SupplierAccountTierPricingSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'name' in data:
            name = data['name'].strip() or account.name
            if name != account.name:
                account.name = name
                account.save(update_fields=['name', 'updated_at'])
        save_supplier_account_tier_pricing(
            account.id,
            tenant_account_id,
            data['tiers'],
        )
        return Response(
            {
                'name': account.name,
                'tiers': get_supplier_account_tier_pricing(
                    account.id,
                    tenant_account_id,
                ),
            },
        )


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'username', 'email', 'created_at']
    ordering = ['id']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = User.objects.all()
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return qs

    def perform_create(self, serializer):
        user = serializer.save()
        _send_reset_email(user)

    def perform_update(self, serializer):
        old_email = serializer.instance.email
        user = serializer.save()
        if user.email != old_email:
            _send_reset_email(user)

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        # Always load from the `users` table (not a stale JWT user instance).
        user = (
            User.objects.filter(pk=request.user.pk)
            .select_related('account')
            .first()
        )
        if user is None:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UserSerializer(user)
        return Response(serializer.data)


class PasswordResetConfirmView(GenericAPIView):
    """POST /api/reset-password/confirm/ with { token, password }"""
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'detail': 'Password has been set successfully.'},
            status=status.HTTP_200_OK,
        )
