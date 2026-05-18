from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import HasAccount

from .models import BookingGroup, BookingItem, BookingStatus, FormTemplate
from .serializers import (
    BookingItemSerializer,
    BookingStatusSerializer,
    FormTemplateSerializer,
)


class BookingStatusViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = BookingStatusSerializer

    def get_queryset(self):
        return BookingStatus.objects.filter(account_id=self.request.user.account_id)

    def perform_create(self, serializer):
        aid = self.request.user.account_id
        max_order = (
            BookingStatus.objects.filter(account_id=aid)
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
                {'order': ['Expected a list of status IDs.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        aid = request.user.account_id
        for idx, status_id in enumerate(ids):
            BookingStatus.objects.filter(pk=status_id, account_id=aid).update(sort_order=idx)
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
        status_id = self.request.query_params.get('status')
        if status_id:
            qs = qs.filter(status_id=status_id)
        return qs

    def perform_create(self, serializer):
        booking_status = serializer.validated_data['status']
        max_order = (
            booking_status.items.filter(account_id=self.request.user.account_id)
            .order_by('-sort_order')
            .values_list('sort_order', flat=True)
            .first()
            or 0
        )
        serializer.save(sort_order=max_order + 1)

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        item = self.get_object()
        status_id = request.data.get('status')
        sort_order = request.data.get('sort_order', 0)
        if status_id is None:
            return Response(
                {'status': ['Status ID is required.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        booking_status = BookingStatus.objects.filter(
            pk=status_id,
            account_id=request.user.account_id,
        ).first()
        if booking_status is None:
            return Response(
                {'status': ['Status not found.']},
                status=status.HTTP_404_NOT_FOUND,
            )
        item.status = booking_status
        item.account_id = booking_status.account_id
        item.sort_order = sort_order
        item.save(update_fields=['status', 'account_id', 'sort_order'])
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=['delete'], url_path=r'groups/(?P<group_id>[0-9]+)')
    def delete_group(self, request, pk=None, group_id=None):
        item = self.get_object()
        group = get_object_or_404(BookingGroup, pk=group_id, booking=item)
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Bulk-update sort_order (and optionally status) for multiple items."""
        updates = request.data.get('items', [])
        if not isinstance(updates, list):
            return Response(
                {'items': ['Expected a list of {id, status, sort_order}.']},
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
            if 'status' in entry:
                new_status_id = entry['status']
                if not BookingStatus.objects.filter(
                    pk=new_status_id,
                    account_id=request.user.account_id,
                ).exists():
                    continue
                fields['status_id'] = new_status_id
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
