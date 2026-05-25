from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SystemNotification
from .serializers import SystemNotificationPublicSerializer


class ActiveSystemNotificationsView(APIView):
    """Notifications visible in the app header today."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        rows = (
            SystemNotification.objects.filter(
                start_date__lte=today,
                end_date__gte=today,
            )
            .order_by('-start_date', '-id')
        )
        data = SystemNotificationPublicSerializer(rows, many=True).data
        return Response(data)
