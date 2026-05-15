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
from .serializers import (
    AccountSerializer,
    EmailTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    UserCreateSerializer,
    UserSerializer,
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
        qs = Account.objects.select_related('supplier_type')
        supplier_type = self.request.query_params.get('supplier_type', '').strip()
        if supplier_type:
            qs = qs.filter(supplier_type_id=supplier_type)
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(status__icontains=search),
            )
        return qs

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at', 'updated_at'])


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
