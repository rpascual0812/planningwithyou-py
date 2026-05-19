from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import HasAccount, HasCompany

from .models import CalendarStatus
from .scope import calendar_events_for_user
from .serializers import CalendarSerializer, CalendarStatusSerializer


class CalendarStatusViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = CalendarStatusSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'title', 'sort_order', 'created_at']
    ordering = ['sort_order', 'id']

    def get_queryset(self):
        return CalendarStatus.objects.filter(account_id=self.request.user.account_id)

    def perform_create(self, serializer):
        aid = self.request.user.account_id
        max_order = (
            CalendarStatus.objects.filter(account_id=aid)
            .order_by('-sort_order')
            .values_list('sort_order', flat=True)
            .first()
            or 0
        )
        serializer.save(
            account_id=aid,
            created_by=self.request.user,
            sort_order=max_order + 1,
        )

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at'])

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
            CalendarStatus.objects.filter(pk=status_id, account_id=aid).update(
                sort_order=idx,
            )
        return Response({'status': 'ok'})


class CalendarViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany]
    serializer_class = CalendarSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'title', 'start', 'end', 'created_at']
    ordering = ['start', 'id']

    def get_queryset(self):
        qs = calendar_events_for_user(self.request.user).select_related(
            'status',
            'contact',
            'booking',
        )
        start = self.request.query_params.get('start')
        end = self.request.query_params.get('end')
        if start:
            qs = qs.filter(end__gte=start)
        if end:
            qs = qs.filter(start__lte=end)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            account_id=self.request.user.account_id,
            company_id=self.request.user.company_id,
            created_by=self.request.user,
        )

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at'])
