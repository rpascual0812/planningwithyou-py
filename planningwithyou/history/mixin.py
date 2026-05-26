from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response

from bookings.models import History

from .serializers import HistorySerializer


class HistoryListMixin:
    """Add ``GET …/{id}/history/`` to a viewset."""

    history_resource_type: str = ''

    @action(detail=True, methods=['get'], url_path='history')
    def change_history(self, request, pk=None):
        obj = self.get_object()
        account_id = self._history_account_id(obj, request)
        filters = Q(
            account_id=account_id,
            resource_type=self.history_resource_type,
            resource_id=obj.pk,
        )
        if self.history_resource_type == History.ResourceType.BOOKING:
            filters |= Q(account_id=account_id, booking_id=obj.pk)
        rows = (
            History.objects.filter(filters)
            .distinct()
            .select_related('actor')
            .order_by('-created_at', '-id')
        )
        return Response(HistorySerializer(rows, many=True).data)

    def _history_account_id(self, obj, request) -> int:
        account_id = getattr(obj, 'account_id', None)
        if account_id is not None:
            return account_id
        return request.user.account_id
