from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import HasAccount

from django.shortcuts import get_object_or_404

from .models import BookingColumn, BookingGroup, BookingItem, FormTemplate
from .serializers import (
    BookingColumnSerializer,
    BookingItemSerializer,
    FormTemplateSerializer,
)


class BookingColumnViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = BookingColumnSerializer

    def get_queryset(self):
        return BookingColumn.objects.filter(account_id=self.request.user.account_id)

    def perform_create(self, serializer):
        aid = self.request.user.account_id
        max_order = (
            BookingColumn.objects.filter(account_id=aid)
            .order_by('-sort_order')
            .values_list('sort_order', flat=True)
            .first()
            or 0
        )
        serializer.save(account_id=aid, sort_order=max_order + 1)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        ids = request.data.get('order', [])
        if not isinstance(ids, list):
            return Response(
                {'order': ['Expected a list of column IDs.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        aid = request.user.account_id
        for idx, col_id in enumerate(ids):
            BookingColumn.objects.filter(pk=col_id, account_id=aid).update(sort_order=idx)
        return Response({'status': 'ok'})


class BookingItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = BookingItemSerializer

    def get_queryset(self):
        aid = self.request.user.account_id
        qs = BookingItem.objects.filter(account_id=aid).prefetch_related(
            'groups',
            'lines__booking_group',
        )
        column_id = self.request.query_params.get('column')
        if column_id:
            qs = qs.filter(column_id=column_id)
        return qs

    def perform_create(self, serializer):
        column = serializer.validated_data['column']
        max_order = (
            column.items.filter(account_id=self.request.user.account_id)
            .order_by('-sort_order')
            .values_list('sort_order', flat=True)
            .first()
            or 0
        )
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
        column = BookingColumn.objects.filter(
            pk=column_id,
            account_id=request.user.account_id,
        ).first()
        if column is None:
            return Response(
                {'column': ['Column not found.']},
                status=status.HTTP_404_NOT_FOUND,
            )
        item.column = column
        item.account_id = column.account_id
        item.sort_order = sort_order
        item.save(update_fields=['column', 'account_id', 'sort_order'])
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=['delete'], url_path=r'groups/(?P<group_id>[0-9]+)')
    def delete_group(self, request, pk=None, group_id=None):
        item = self.get_object()
        group = get_object_or_404(BookingGroup, pk=group_id, booking=item)
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Bulk-update sort_order (and optionally column) for multiple items."""
        updates = request.data.get('items', [])
        if not isinstance(updates, list):
            return Response(
                {'items': ['Expected a list of {id, column, sort_order}.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        base_qs = self.get_queryset()
        for entry in updates:
            item_id = entry.get('id')
            if item_id is None:
                continue
            if not base_qs.filter(pk=item_id).exists():
                continue
            fields = {}
            if 'column' in entry:
                col_id = entry['column']
                if not BookingColumn.objects.filter(
                    pk=col_id,
                    account_id=request.user.account_id,
                ).exists():
                    continue
                fields['column_id'] = col_id
                fields['account_id'] = request.user.account_id
            if 'sort_order' in entry:
                fields['sort_order'] = entry['sort_order']
            if fields:
                BookingItem.objects.filter(pk=item_id, account_id=request.user.account_id).update(
                    **fields,
                )
        return Response({'status': 'ok'})


class FormTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = FormTemplateSerializer

    def get_queryset(self):
        return FormTemplate.objects.filter(
            account_id=self.request.user.account_id,
        ).prefetch_related('fields__options')
