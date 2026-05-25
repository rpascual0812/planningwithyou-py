from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from planningwithyou.permissions import HasAccount, HasCompany
from planningwithyou.template_placeholders import (
    DEFAULT_PASSWORD_RESET_BODY_HTML,
    DEFAULT_PASSWORD_RESET_SUBJECT,
    DEFAULT_VERIFY_EMAIL_BODY_HTML,
    DEFAULT_VERIFY_EMAIL_SUBJECT,
    EMAIL_TEMPLATE_PASSWORD_RESET,
    EMAIL_TEMPLATE_VERIFY_EMAIL,
    apply_template_placeholders,
    company_template_context,
    user_template_context,
)

from emails.mail import create_and_queue_email
from emails.models import EmailTemplate
from emails.tasks import send_email_task

from .models import Account, EmailVerificationToken, PasswordResetToken
from .scope import users_for_user
from .registration_serializers import RegisterSerializer
from .serializers import (
    AccountSerializer,
    EmailTokenObtainPairSerializer,
    EmailVerifySerializer,
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
    reset_url = f'{settings.FRONTEND_URL}/reset-password/{reset.token}'
    lifetime = settings.PASSWORD_RESET_TOKEN_LIFETIME_HOURS
    company = getattr(user, 'company', None)
    if company is None and user.company_id:
        from companies.models import Company

        company = Company.objects.filter(pk=user.company_id).first()
    context = {
        **user_template_context(user),
        **company_template_context(company),
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
        created_by=user,
    )
    send_email_task.delay(log.pk)


def _send_verification_email(user):
    EmailVerificationToken.objects.filter(user=user, used=False).update(used=True)
    verification = EmailVerificationToken.objects.create(user=user)
    verify_url = f'{settings.FRONTEND_URL}/verify-email/{verification.token}'
    lifetime = getattr(settings, 'EMAIL_VERIFICATION_TOKEN_LIFETIME_HOURS', 72)
    company = getattr(user, 'company', None)
    if company is None and user.company_id:
        from companies.models import Company

        company = Company.objects.filter(pk=user.company_id).first()
    context = {
        **user_template_context(user),
        **company_template_context(company),
        'verify_url': verify_url,
        'lifetime': str(lifetime),
    }

    tmpl = (
        EmailTemplate.objects.filter(
            name=EMAIL_TEMPLATE_VERIFY_EMAIL,
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
            tmpl.subject.strip() or DEFAULT_VERIFY_EMAIL_SUBJECT,
            context,
        )
        body = apply_template_placeholders(tmpl.body, context)
        if not body.strip():
            body = apply_template_placeholders(DEFAULT_VERIFY_EMAIL_BODY_HTML, context)
    else:
        subject = apply_template_placeholders(DEFAULT_VERIFY_EMAIL_SUBJECT, context)
        body = apply_template_placeholders(DEFAULT_VERIFY_EMAIL_BODY_HTML, context)

    log = create_and_queue_email(
        to=[user.email],
        subject=subject,
        body=body,
        account=getattr(user, 'account', None),
        created_by=None,
    )
    send_email_task.delay(log.pk)


class AccountViewSet(viewsets.ModelViewSet):
    """Accounts (tenant organizations), filterable by supplier type."""

    permission_classes = [IsAuthenticated]
    serializer_class = AccountSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']
    ordering = ['name']

    def get_queryset(self):
        qs = Account.objects.select_related('country')
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

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
            Account.objects.select_related('country')
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

class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'username', 'email', 'created_at']
    ordering = ['id']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = users_for_user(self.request.user)
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
            .select_related('account', 'company')
            .first()
        )
        if user is None:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UserSerializer(user)
        return Response(serializer.data)


class RegisterView(GenericAPIView):
    """POST /api/register/ — self-service tenant signup."""

    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        _send_verification_email(user)
        return Response(
            {
                'detail': (
                    'Registration successful. Please check your email to verify '
                    'your account before signing in.'
                ),
                'email': user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class EmailVerifyView(GenericAPIView):
    """POST /api/verify-email/ with { token } — verify email and return JWT."""

    permission_classes = [AllowAny]
    serializer_class = EmailVerifySerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'detail': 'Email verified successfully.',
            },
            status=status.HTTP_200_OK,
        )


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
