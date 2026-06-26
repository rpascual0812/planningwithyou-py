from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import HasAccount

from .models import UserNotification
from .serializers import UserNotificationSerializer


class UserNotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Per-user in-app notifications."""

    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = UserNotificationSerializer

    def get_queryset(self):
        qs = UserNotification.objects.filter(user_id=self.request.user.pk)
        unread_only = self.request.query_params.get('unread_only', '').lower() in (
            '1',
            'true',
            'yes',
        )
        if unread_only:
            qs = qs.unread()
        return qs.order_by('-created_at', '-id')

    def retrieve(self, request, *args, **kwargs):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at', 'updated_at'])
        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        notification = self.get_object()
        notification.deleted_at = timezone.now()
        notification.save(update_fields=['deleted_at', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = UserNotification.objects.filter(
            user_id=request.user.pk,
            read_at__isnull=True,
        ).count()
        return Response({'count': count})

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at', 'updated_at'])
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
