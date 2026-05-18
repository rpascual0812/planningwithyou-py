from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import HasAccount

from .models import EmailLog, EmailTemplate
from .serializers import EmailLogSerializer, EmailTemplateSerializer
from .tasks import send_email_task


class EmailLogViewSet(viewsets.ModelViewSet):
    """CRUD + resend for email logs."""
    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = EmailLogSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'status', 'created_at', 'sent_at']
    ordering = ['-created_at']

    def get_queryset(self):
        aid = self.request.user.account_id
        qs = EmailLog.objects.filter(account_id=aid)
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

    def perform_create(self, serializer):
        log = serializer.save(
            status=EmailLog.Status.QUEUED,
            account_id=self.request.user.account_id,
            email_from=settings.MAILJET_SEND_FROM,
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
            email_from=settings.MAILJET_SEND_FROM,
        )
        send_email_task.delay(log.pk)
        return Response(
            self.get_serializer(log).data,
            status=status.HTTP_200_OK,
        )


class EmailTypedTemplateViewSet(viewsets.ModelViewSet):
    """CRUD for email templates scoped to a single ``template_type``."""

    permission_classes = [IsAuthenticated, HasAccount]
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
        serializer.save(
            template_type=self.template_type,
            account_id=self.request.user.account_id,
        )

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at', 'updated_at'])


class EmailUserTemplateViewSet(EmailTypedTemplateViewSet):
    """CRUD for email templates with template_type fixed to ``users``."""

    template_type = EmailTemplate.TemplateType.USERS


class EmailBookingTemplateViewSet(EmailTypedTemplateViewSet):
    """CRUD for email templates with template_type fixed to ``bookings``."""

    template_type = EmailTemplate.TemplateType.BOOKINGS
