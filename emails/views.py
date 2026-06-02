from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.history.core import request_metadata
from planningwithyou.history.mixin import HistoryListMixin
from planningwithyou.history.record import (
    record_resource_create,
    record_resource_delete,
    record_resource_update,
)
from planningwithyou.history.snapshots import (
    EMAIL_TEMPLATE_FIELDS,
    diff_simple,
    snapshot_email_template,
)
from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .models import EmailLog, EmailTemplate
from users.company_access import effective_company_id

from .scope import email_logs_for_platform_admin, email_logs_for_user
from .serializers import EmailLogSerializer, EmailTemplateSerializer
from .gmail_service import resolve_sender_email
from .tasks import send_email_task


class EmailLogViewSet(viewsets.ModelViewSet):
    """CRUD + resend for email logs."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    serializer_class = EmailLogSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'status', 'created_at', 'sent_at']
    ordering = ['-created_at']

    class Pagination(PageNumberPagination):
        page_size = 10

    pagination_class = Pagination

    def _is_platform_scope(self) -> bool:
        return self.request.query_params.get('platform_scope', '').lower() in (
            '1',
            'true',
            'yes',
        )

    def _uses_admin_emails(self) -> bool:
        if self._is_platform_scope():
            return True
        pk = self.kwargs.get('pk')
        if not pk:
            return False
        account_id = getattr(self.request.user, 'account_id', None)
        if account_id is None:
            return False
        log_account_id = (
            EmailLog.objects.filter(pk=pk)
            .values_list('account_id', flat=True)
            .first()
        )
        return log_account_id is not None and log_account_id != account_id

    def get_feature_key(self, request):
        if self._uses_admin_emails():
            return 'admin_emails'
        return 'emails'

    def get_permissions(self):
        if self._uses_admin_emails():
            return [IsAuthenticated(), FeatureAccess()]
        return super().get_permissions()

    def _company_id_filter(self):
        raw = self.request.query_params.get('company_id', '').strip()
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def get_queryset(self):
        if self._is_platform_scope():
            qs = email_logs_for_platform_admin(
                self.request.user,
                company_id=self._company_id_filter(),
            )
        else:
            qs = email_logs_for_user(
                self.request.user,
                company_id=self._company_id_filter(),
            )
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(to__icontains=search)
                | Q(subject__icontains=search)
                | Q(body__icontains=search)
                | Q(email_from__icontains=search)
            )
        status_filter = self.request.query_params.get('status', '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def list(self, request, *args, **kwargs):
        paginated = (
            request.query_params.get('paginated', '').strip().lower() in ('1', 'true', 'yes')
            or request.query_params.get('page', '').strip() != ''
        )
        if not paginated:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        log = serializer.save(
            status=EmailLog.Status.QUEUED,
            account_id=self.request.user.account_id,
            company_id=self.request.user.company_id,
            created_by=self.request.user,
            email_from=resolve_sender_email(
                self.request.user.account_id,
                self.request.user.company_id,
            )
            or settings.MAILJET_SEND_FROM,
        )
        send_email_task.delay(log.pk)

    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """POST /api/emails/{id}/resend/ — optionally edit fields, then re-queue."""
        log = self.get_object()
        serializer = self.get_serializer(log, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            status=EmailLog.Status.QUEUED,
            error='',
            email_from=resolve_sender_email(
                request.user.account_id,
                request.user.company_id,
            )
            or settings.MAILJET_SEND_FROM,
        )
        send_email_task.delay(log.pk)
        return Response(
            self.get_serializer(log).data,
            status=status.HTTP_200_OK,
        )


class EmailTypedTemplateViewSet(HistoryListMixin, viewsets.ModelViewSet):
    """CRUD for email templates scoped to a single ``template_type``."""

    history_resource_type = 'email_template'
    feature_key = 'email_templates'
    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    serializer_class = EmailTemplateSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'name', 'created_at', 'updated_at']
    ordering = ['name']
    template_type: str = ''

    def get_queryset(self):
        aid = self.request.user.account_id
        qs = EmailTemplate.objects.filter(
            template_type=self.template_type,
            deleted_at__isnull=True,
            account_id=aid,
        )
        raw = self.request.query_params.get('company_id', '').strip()
        requested = int(raw) if raw.isdigit() else None
        company_id = effective_company_id(self.request.user, requested)
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(title__icontains=search)
                | Q(subject__icontains=search)
                | Q(body__icontains=search),
            )
        return qs

    def perform_create(self, serializer):
        company_id = serializer.validated_data.get('company_id')
        if company_id is None:
            company_id = self.request.user.company_id
        template = serializer.save(
            template_type=self.template_type,
            account_id=self.request.user.account_id,
            company_id=company_id,
            is_default=False,
        )
        record_resource_create(
            account_id=template.account_id,
            resource_type='email_template',
            resource_id=template.pk,
            snapshot=snapshot_email_template(template),
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )

    def perform_update(self, serializer):
        before = snapshot_email_template(serializer.instance)
        company_id = serializer.validated_data.get('company_id')
        if company_id is None and self.request.user.company_id:
            template = serializer.save(company_id=self.request.user.company_id)
        else:
            template = serializer.save()
        changes = diff_simple(
            before,
            snapshot_email_template(template),
            EMAIL_TEMPLATE_FIELDS,
        )
        request = self.request

        def _record():
            record_resource_update(
                account_id=template.account_id,
                resource_type='email_template',
                resource_id=template.pk,
                changes=changes,
                actor=request.user,
                metadata=request_metadata(request),
            )

        transaction.on_commit(_record)

    def perform_destroy(self, instance):
        if instance.is_default:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Default email templates cannot be deleted.')
        record_resource_delete(
            account_id=instance.account_id,
            resource_type='email_template',
            resource_id=instance.pk,
            changes={'name': instance.name, 'title': instance.title},
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at', 'updated_at'])


class EmailUserTemplateViewSet(EmailTypedTemplateViewSet):
    """CRUD for email templates with template_type fixed to ``users``."""

    template_type = EmailTemplate.TemplateType.USERS


class EmailBookingTemplateViewSet(EmailTypedTemplateViewSet):
    """CRUD for email templates with template_type fixed to ``bookings``."""

    template_type = EmailTemplate.TemplateType.BOOKINGS


class EmailCalendarTemplateViewSet(EmailTypedTemplateViewSet):
    """CRUD for email templates with template_type fixed to ``calendar``."""

    template_type = EmailTemplate.TemplateType.CALENDAR
