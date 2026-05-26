from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import IsAdmin

from .models import SystemNotification
from .serializers import SystemNotificationSerializer


class SystemNotificationAdminViewSet(viewsets.ModelViewSet):
    """Platform admin CRUD for system-wide header notifications."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = SystemNotificationSerializer

    def get_queryset(self):
        qs = SystemNotification.objects.select_related('created_by').order_by(
            '-start_date',
            '-id',
        )
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search) | Q(message__icontains=search),
            )
        status = self.request.query_params.get('status', '').strip()
        now = timezone.now()
        if status == 'active':
            qs = qs.filter(start_date__lte=now, end_date__gte=now)
        elif status == 'scheduled':
            qs = qs.filter(start_date__gt=now)
        elif status == 'expired':
            qs = qs.filter(end_date__lt=now)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at'])
