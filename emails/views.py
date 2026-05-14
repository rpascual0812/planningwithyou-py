from django.db.models import Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import EmailLog
from .serializers import EmailLogSerializer
from .tasks import send_email_task


class EmailLogViewSet(viewsets.ModelViewSet):
    """CRUD + resend for email logs."""
    permission_classes = [IsAuthenticated]
    serializer_class = EmailLogSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'status', 'created_at', 'sent_at']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = EmailLog.objects.all()
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(to__icontains=search)
                | Q(subject__icontains=search)
                | Q(email_from__icontains=search)
            )
        status_filter = self.request.query_params.get('status', '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        log = serializer.save(status=EmailLog.Status.QUEUED)
        send_email_task.delay(log.pk)

    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """POST /api/emails/{id}/resend/ — optionally edit fields, then re-queue."""
        log = self.get_object()
        serializer = self.get_serializer(log, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(status=EmailLog.Status.QUEUED, error='')
        send_email_task.delay(log.pk)
        return Response(
            self.get_serializer(log).data,
            status=status.HTTP_200_OK,
        )
