from datetime import datetime, time

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import FeatureAccess

from .admin_error_log_serializers import (
    ErrorLogAdminDetailSerializer,
    ErrorLogAdminListSerializer,
)
from .models import ErrorLog


def _parse_occurred_bound(raw: str, *, end_of_day: bool = False):
    value = raw.strip()
    if not value:
        return None
    parsed_dt = parse_datetime(value)
    if parsed_dt is not None:
        if timezone.is_naive(parsed_dt):
            parsed_dt = timezone.make_aware(parsed_dt, timezone.get_current_timezone())
        return parsed_dt
    parsed_date = parse_date(value)
    if parsed_date is None:
        return None
    bound = datetime.combine(
        parsed_date,
        time.max if end_of_day else time.min,
    )
    return timezone.make_aware(bound, timezone.get_current_timezone())


def filter_admin_error_logs(queryset, request):
    qs = queryset
    method = request.query_params.get('method', '').strip().upper()
    if method:
        qs = qs.filter(method__iexact=method)

    status_raw = request.query_params.get('status_code', '').strip()
    if status_raw.isdigit():
        qs = qs.filter(status_code=int(status_raw))

    occurred_from = _parse_occurred_bound(
        request.query_params.get('occurred_from', ''),
        end_of_day=False,
    )
    if occurred_from is not None:
        qs = qs.filter(created_at__gte=occurred_from)

    occurred_to = _parse_occurred_bound(
        request.query_params.get('occurred_to', ''),
        end_of_day=True,
    )
    if occurred_to is not None:
        qs = qs.filter(created_at__lte=occurred_to)

    search = request.query_params.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(exception_message__icontains=search)
            | Q(exception_type__icontains=search)
            | Q(path__icontains=search),
        )
    return qs


class AdminErrorLogPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class ErrorLogAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Platform admin list/review of persisted API error logs."""

    feature_key = 'admin_error_logs'
    permission_classes = [IsAuthenticated, FeatureAccess]
    pagination_class = AdminErrorLogPagination

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ErrorLogAdminDetailSerializer
        return ErrorLogAdminListSerializer

    def get_queryset(self):
        qs = ErrorLog.objects.select_related('user', 'account', 'resolved_by').order_by(
            '-created_at',
        )
        if self.action == 'list':
            qs = filter_admin_error_logs(qs, self.request)
        return qs

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        log = self.get_object()
        if log.resolved_at is None:
            log.resolved_at = timezone.now()
            log.resolved_by = request.user
            log.save(update_fields=['resolved_at', 'resolved_by_id'])
        serializer = ErrorLogAdminListSerializer(log)
        return Response(serializer.data, status=status.HTTP_200_OK)
