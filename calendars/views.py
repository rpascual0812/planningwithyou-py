from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import filters, mixins, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from users.company_access import effective_company_id

from .notifications import send_calendar_event_email
from .reminders import (
    cancel_appointment_reminders_for_event,
    reschedule_appointment_reminders_for_event,
    schedule_appointment_reminders_for_event,
)
from .models import AppointmentReminder, Calendar, CalendarStatus, ScheduledAppointmentReminder
from .scope import calendar_events_for_user
from .serializers import (
    AppointmentReminderSerializer,
    CalendarSerializer,
    CalendarStatusSerializer,
    ScheduledAppointmentReminderSerializer,
)


class CalendarStatusViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'calendar_settings'
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


class AppointmentReminderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'calendar_settings'
    serializer_class = AppointmentReminderSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'frequency', 'created_at', 'updated_at']
    ordering = ['id']

    def get_queryset(self):
        aid = self.request.user.account_id
        qs = AppointmentReminder.objects.filter(account_id=aid).prefetch_related(
            'calendar_statuses',
        )
        raw = self.request.query_params.get('company_id', '').strip()
        requested = int(raw) if raw.isdigit() else None
        company_id = effective_company_id(self.request.user, requested)
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        status_ids = self._calendar_status_filter_ids()
        if status_ids:
            qs = (
                qs.annotate(_linked_status_count=Count('calendar_statuses', distinct=True))
                .filter(
                    Q(_linked_status_count=0)
                    | Q(calendar_statuses__id__in=status_ids),
                )
                .distinct()
            )
        return qs

    def _calendar_status_filter_ids(self) -> list[int]:
        raw = self.request.query_params.get('calendar_status_ids', '').strip()
        if not raw:
            return []
        ids: list[int] = []
        for part in raw.split(','):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

    def perform_create(self, serializer):
        raw = self.request.query_params.get('company_id', '').strip()
        requested = int(raw) if raw.isdigit() else None
        company_id = effective_company_id(self.request.user, requested)
        if company_id is None:
            company_id = self.request.user.company_id
        serializer.save(
            account_id=self.request.user.account_id,
            company_id=company_id,
            created_by=self.request.user,
        )

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at'])


class ScheduledAppointmentReminderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """List scheduled appointment reminder emails; cancel or restore future sends."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'emails'
    serializer_class = ScheduledAppointmentReminderSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'send_at', 'status', 'created_at', 'sent_at']
    ordering = ['-send_at', 'id']

    class Pagination(PageNumberPagination):
        page_size = 20

    pagination_class = Pagination

    def get_queryset(self):
        aid = self.request.user.account_id
        qs = ScheduledAppointmentReminder.objects.filter(account_id=aid).select_related(
            'calendar_event',
            'appointment_reminder',
            'email_log',
        )
        raw = self.request.query_params.get('company_id', '').strip()
        requested = int(raw) if raw.isdigit() else None
        company_id = effective_company_id(self.request.user, requested)
        if company_id is not None:
            qs = qs.filter(company_id=company_id)

        timing = self.request.query_params.get('timing', '').strip().lower()
        now = timezone.now()
        if timing == 'future':
            qs = qs.filter(send_at__gt=now)
        elif timing == 'past':
            qs = qs.filter(send_at__lte=now)

        status_filter = self.request.query_params.get('status', '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)

        include_deleted = self.request.query_params.get('include_deleted', '').lower() in (
            '1',
            'true',
            'yes',
        )
        if not include_deleted:
            qs = qs.filter(deleted_at__isnull=True)

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(recipient_email__icontains=search)
                | Q(recipient_name__icontains=search)
                | Q(calendar_event__title__icontains=search)
            )
        return qs

    def list(self, request, *args, **kwargs):
        paginated = (
            request.query_params.get('paginated', '').strip().lower() in ('1', 'true', 'yes')
            or request.query_params.get('page', '').strip() != ''
        )
        if not paginated:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != ScheduledAppointmentReminder.Status.PENDING:
            return Response(
                {'detail': 'Only pending reminders can be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.send_at <= timezone.now():
            return Response(
                {'detail': 'Past reminders cannot be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        instance = self.get_object()
        if instance.deleted_at is None:
            return Response({'detail': 'Reminder is not cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        if instance.status != ScheduledAppointmentReminder.Status.PENDING:
            return Response(
                {'detail': 'Only pending reminders can be restored.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.send_at <= timezone.now():
            return Response(
                {'detail': 'Cannot restore a reminder whose send time has passed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.deleted_at = None
        instance.save(update_fields=['deleted_at', 'updated_at'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class CalendarViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'calendar'
    serializer_class = CalendarSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'title', 'start', 'end', 'created_at']
    ordering = ['start', 'id']

    def get_queryset(self):
        qs = calendar_events_for_user(self.request.user).select_related(
            'status',
            'contact',
            'quotation',
        )
        start = self.request.query_params.get('start')
        end = self.request.query_params.get('end')
        if start:
            qs = qs.filter(end__gte=start)
        if end:
            qs = qs.filter(start__lte=end)
        return qs

    def perform_create(self, serializer):
        event = serializer.save(
            account_id=self.request.user.account_id,
            company_id=self.request.user.company_id,
            created_by=self.request.user,
        )
        send_calendar_event_email(
            event,
            template_name='calendar_event_creation',
            fallback_subject='Scheduled event',
        )
        schedule_appointment_reminders_for_event(event)

    def perform_update(self, serializer):
        event = serializer.save()
        send_calendar_event_email(
            event,
            template_name='calendar_event_updated',
            fallback_subject='Event updated',
        )
        reschedule_appointment_reminders_for_event(event)

    def perform_destroy(self, instance):
        cancel_appointment_reminders_for_event(instance)
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at'])
