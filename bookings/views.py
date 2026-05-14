from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import BookingColumn, BookingItem, FormTemplate
from .serializers import (
    BookingColumnSerializer,
    BookingItemSerializer,
    FormTemplateSerializer,
)


class BookingColumnViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BookingColumnSerializer
    queryset = BookingColumn.objects.all()

    def perform_create(self, serializer):
        max_order = BookingColumn.objects.order_by('-sort_order').values_list(
            'sort_order', flat=True,
        ).first() or 0
        serializer.save(sort_order=max_order + 1)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        ids = request.data.get('order', [])
        if not isinstance(ids, list):
            return Response(
                {'order': ['Expected a list of column IDs.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for idx, col_id in enumerate(ids):
            BookingColumn.objects.filter(pk=col_id).update(sort_order=idx)
        return Response({'status': 'ok'})


class BookingItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BookingItemSerializer

    def get_queryset(self):
        qs = BookingItem.objects.all()
        column_id = self.request.query_params.get('column')
        if column_id:
            qs = qs.filter(column_id=column_id)
        return qs

    def perform_create(self, serializer):
        column = serializer.validated_data['column']
        max_order = column.items.order_by('-sort_order').values_list(
            'sort_order', flat=True,
        ).first() or 0
        serializer.save(sort_order=max_order + 1)

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        item = self.get_object()
        column_id = request.data.get('column')
        sort_order = request.data.get('sort_order', 0)
        if column_id is None:
            return Response(
                {'column': ['Column ID is required.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            column = BookingColumn.objects.get(pk=column_id)
        except BookingColumn.DoesNotExist:
            return Response(
                {'column': ['Column not found.']},
                status=status.HTTP_404_NOT_FOUND,
            )
        item.column = column
        item.sort_order = sort_order
        item.save(update_fields=['column', 'sort_order'])
        return Response(self.get_serializer(item).data)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Bulk-update sort_order (and optionally column) for multiple items."""
        updates = request.data.get('items', [])
        if not isinstance(updates, list):
            return Response(
                {'items': ['Expected a list of {id, column, sort_order}.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for entry in updates:
            item_id = entry.get('id')
            if item_id is None:
                continue
            fields = {}
            if 'column' in entry:
                fields['column_id'] = entry['column']
            if 'sort_order' in entry:
                fields['sort_order'] = entry['sort_order']
            if fields:
                BookingItem.objects.filter(pk=item_id).update(**fields)
        return Response({'status': 'ok'})


class FormTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FormTemplateSerializer
    queryset = FormTemplate.objects.prefetch_related('fields__options').all()
