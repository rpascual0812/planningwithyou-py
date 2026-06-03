from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from rest_framework import filters, parsers, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from planningwithyou.history.core import request_metadata
from planningwithyou.history.mixin import HistoryListMixin
from planningwithyou.history.record import (
    record_resource_create,
    record_resource_delete,
    record_resource_update,
)
from planningwithyou.history.snapshots import (
    ACCOUNT_FIELDS,
    USER_FIELDS,
    diff_simple,
    snapshot_account,
    snapshot_user,
)
from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .role_serializers import (
    FEATURE_LABELS,
    RoleSerializer,
    RoleWriteSerializer,
    roles_queryset_for_account,
)
from .roles import TENANT_FEATURE_KEYS, default_role_for_account
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

from subscriptions.account_plan import active_subscription_plan_for_account

from .seat_usage import (
    SEAT_LIMIT_MESSAGE,
    account_at_user_seat_limit,
    active_user_count_for_account,
    team_seats_for_account,
)

from emails.mail import create_and_queue_email
from emails.models import EmailTemplate
from emails.tasks import send_email_task

from .models import Account, EmailVerificationToken, PasswordResetToken
from .scope import users_for_user
from .registration_serializers import RegisterSerializer
from .jwt import issue_tokens_for_user
from .serializers import (
    AccountSerializer,
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    EmailVerifySerializer,
    PasswordResetConfirmSerializer,
    UserCreateSerializer,
    UserSerializer,
)

User = get_user_model()


class UsersPagination(PageNumberPagination):
    page_size = 10


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
        email_template=tmpl,
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
        email_template=tmpl,
        account=getattr(user, 'account', None),
        created_by=None,
    )
    send_email_task.delay(log.pk)


class AccountViewSet(HistoryListMixin, viewsets.ModelViewSet):
    """Accounts (tenant organizations), filterable by supplier type."""

    history_resource_type = 'account'
    feature_key = 'account_settings'
    permission_classes = [IsAuthenticated, FeatureAccess]
    serializer_class = AccountSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']
    ordering = ['name']

    def get_queryset(self):
        qs = Account.objects.select_related('country').filter(deleted_at__isnull=True)
        account_id = getattr(self.request.user, 'account_id', None)
        if account_id is not None:
            qs = qs.filter(pk=account_id)
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_update(self, serializer):
        before = snapshot_account(serializer.instance)
        account = serializer.save()
        changes = diff_simple(before, snapshot_account(account), ACCOUNT_FIELDS)
        request = self.request

        def _record():
            record_resource_update(
                account_id=account.pk,
                resource_type='account',
                resource_id=account.pk,
                changes=changes,
                actor=request.user,
                metadata=request_metadata(request),
            )

        transaction.on_commit(_record)

    def perform_destroy(self, instance):
        record_resource_delete(
            account_id=instance.pk,
            resource_type='account',
            resource_id=instance.pk,
            changes={'name': instance.name},
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )
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

class UserViewSet(HistoryListMixin, viewsets.ModelViewSet):
    history_resource_type = 'user'
    feature_key = 'users'
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'username', 'email', 'created_at']
    ordering = ['id']
    pagination_class = UsersPagination

    def get_permissions(self):
        if self.action in ('me', 'change_password'):
            return [IsAuthenticated(), HasAccount()]
        return [IsAuthenticated(), HasAccount(), HasCompany(), FeatureAccess()]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def _company_id_filter(self) -> int | None:
        raw = self.request.query_params.get('company_id', '').strip()
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def get_queryset(self):
        qs = users_for_user(
            self.request.user,
            company_id=self._company_id_filter(),
        )
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return qs.select_related('role')

    @action(detail=False, methods=['get'], url_path='seat-usage')
    def seat_usage(self, request):
        account_id = request.user.account_id
        active_count = active_user_count_for_account(account_id)
        team_seats = team_seats_for_account(account_id)
        return Response(
            {
                'active_users_count': active_count,
                'team_seats': team_seats,
                'at_seat_limit': active_count >= team_seats,
            },
        )

    def perform_create(self, serializer):
        account_id = self.request.user.account_id
        if active_subscription_plan_for_account(account_id) == 'free':
            raise PermissionDenied(
                'Adding users requires a paid subscription plan.',
            )
        if account_at_user_seat_limit(account_id):
            raise PermissionDenied(SEAT_LIMIT_MESSAGE)
        user = serializer.save()
        if user.role_id is None:
            role = default_role_for_account(account_id)
            if role is not None:
                user.role = role
                user.save(update_fields=['role'])
        record_resource_create(
            account_id=account_id,
            resource_type='user',
            resource_id=user.pk,
            snapshot=snapshot_user(user),
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )
        _send_reset_email(user)

    def perform_destroy(self, instance):
        record_resource_delete(
            account_id=instance.account_id,
            resource_type='user',
            resource_id=instance.pk,
            changes={
                'username': instance.username,
                'email': instance.email,
            },
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at', 'updated_at'])

    def perform_update(self, serializer):
        instance = serializer.instance
        new_is_active = serializer.validated_data.get('is_active', instance.is_active)
        if not instance.is_active and new_is_active:
            if account_at_user_seat_limit(self.request.user.account_id):
                raise PermissionDenied(SEAT_LIMIT_MESSAGE)
        before = snapshot_user(instance)
        old_email = instance.email
        user = serializer.save()
        if user.email != old_email:
            _send_reset_email(user)
        changes = diff_simple(before, snapshot_user(user), USER_FIELDS)
        request = self.request

        def _record():
            record_resource_update(
                account_id=user.account_id,
                resource_type='user',
                resource_id=user.pk,
                changes=changes,
                actor=request.user,
                metadata=request_metadata(request),
            )

        transaction.on_commit(_record)

    @action(detail=False, methods=['get', 'patch'], url_path='me')
    def me(self, request):
        # Always load from the `users` table (not a stale JWT user instance).
        user = (
            User.objects.filter(pk=request.user.pk)
            .select_related('account', 'company', 'role')
            .prefetch_related('role__permissions')
            .first()
        )
        if user is None:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if request.method == 'GET':
            return Response(UserSerializer(user, context={'request': request}).data)

        if request.data.get('complete_product_tour') is True:
            user.tour_completed_at = timezone.now()
            user.save(update_fields=['tour_completed_at', 'updated_at'])
            return Response(
                UserSerializer(user, context={'request': request}).data,
            )
        if request.data.get('restart_product_tour') is True:
            user.tour_completed_at = None
            user.save(update_fields=['tour_completed_at', 'updated_at'])
            return Response(
                UserSerializer(user, context={'request': request}).data,
            )

        allowed_keys = {
            'first_name',
            'last_name',
            'username',
            'email',
            'photo',
            'photo_upload',
        }
        if hasattr(request.data, 'keys'):
            payload = {k: request.data[k] for k in request.data.keys() if k in allowed_keys}
        else:
            payload = dict(request.data)

        serializer = UserSerializer(
            user,
            data=payload,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        before = snapshot_user(user)
        updated = serializer.save()
        changes = diff_simple(before, snapshot_user(updated), USER_FIELDS)
        if changes:

            def _record():
                record_resource_update(
                    account_id=updated.account_id,
                    resource_type='user',
                    resource_id=updated.pk,
                    changes=changes,
                    actor=request.user,
                    metadata=request_metadata(request),
                )

            transaction.on_commit(_record)
        return Response(
            UserSerializer(updated, context={'request': request}).data,
        )

    @action(detail=False, methods=['post'], url_path='me/change-password')
    def change_password(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Password updated successfully.'})


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
        tokens = issue_tokens_for_user(user)
        return Response(
            {
                **tokens,
                'detail': 'Email verified successfully.',
            },
            status=status.HTTP_200_OK,
        )


class RoleViewSet(viewsets.ModelViewSet):
    """Per-account roles and feature permissions (Settings → Roles)."""

    feature_key = 'roles_permissions'
    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        return roles_queryset_for_account(self.request.user.account_id)

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RoleWriteSerializer
        return RoleSerializer

    def perform_destroy(self, instance):
        if instance.name == 'Owner':
            raise ValidationError({'detail': 'The Owner role cannot be deleted.'})
        if instance.users.filter(deleted_at__isnull=True).exists():
            raise ValidationError(
                {'detail': 'Reassign users before deleting this role.'},
            )
        instance.delete()

    @action(detail=False, methods=['get'], url_path='feature-catalog')
    def feature_catalog(self, request):
        from .roles import feature_catalog_keys_for_user

        return Response(
            [
                {'key': key, 'label': FEATURE_LABELS.get(key, key)}
                for key in feature_catalog_keys_for_user(request.user)
            ],
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
