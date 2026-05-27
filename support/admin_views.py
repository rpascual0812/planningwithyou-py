from django.db.models import Count, OuterRef, Prefetch, Subquery
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import FeatureAccess

from .models import SupportTicket, SupportTicketMessage, SupportTicketRead
from .serializers import (
    SupportTicketAdminUpdateSerializer,
    SupportTicketDetailSerializer,
    SupportTicketMessageCreateSerializer,
    SupportTicketMessageSerializer,
    SupportTicketSerializer,
)
from .services import (
    clear_support_ticket_read,
    create_support_ticket_message,
    mark_support_ticket_read,
    order_support_tickets_for_viewer,
)


class SupportTicketAdminViewSet(viewsets.ModelViewSet):
    """Platform admin view of all support tickets."""

    feature_key = 'admin_support'
    permission_classes = [IsAuthenticated, FeatureAccess]
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        last_message = SupportTicketMessage.objects.filter(
            ticket_id=OuterRef('pk'),
        ).order_by('-created_at', '-id')
        qs = (
            SupportTicket.objects.select_related('created_by')
            .annotate(
                _message_count=Count('messages'),
                _last_message_id=Subquery(last_message.values('pk')[:1]),
            )
            .prefetch_related(
                Prefetch(
                    'reads',
                    queryset=SupportTicketRead.objects.filter(user_id=user.pk),
                    to_attr='_prefetched_reads',
                ),
            )
        )
        return order_support_tickets_for_viewer(qs, user)

    def get_serializer_class(self):
        if self.action in ('partial_update', 'update'):
            return SupportTicketAdminUpdateSerializer
        if self.action == 'retrieve':
            return SupportTicketDetailSerializer
        return SupportTicketSerializer

    def _attach_read_state(self, tickets, user):
        ticket_list = list(tickets)
        if not ticket_list:
            return ticket_list
        read_ids = set(
            SupportTicketRead.objects.filter(
                ticket_id__in=[t.pk for t in ticket_list],
                user_id=user.pk,
            ).values_list('ticket_id', flat=True),
        )
        last_message_ids = [
            getattr(t, '_last_message_id', None)
            for t in ticket_list
            if getattr(t, '_last_message_id', None)
        ]
        last_messages = {
            m.pk: m
            for m in SupportTicketMessage.objects.filter(pk__in=last_message_ids)
        }
        for ticket in ticket_list:
            if ticket.pk in read_ids:
                ticket._prefetched_reads = [
                    SupportTicketRead(ticket_id=ticket.pk, user_id=user.pk),
                ]
            else:
                ticket._prefetched_reads = []
            last_id = getattr(ticket, '_last_message_id', None)
            if last_id:
                ticket._last_message = last_messages.get(last_id)
            ticket._message_count = getattr(ticket, '_message_count', 0)
        return ticket_list

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        tickets = self._attach_read_state(queryset, request.user)
        serializer = self.get_serializer(tickets, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        ticket = self.get_object()
        mark_support_ticket_read(ticket, request.user)
        ticket = (
            SupportTicket.objects.select_related('created_by')
            .prefetch_related(
                Prefetch(
                    'messages',
                    queryset=SupportTicketMessage.objects.select_related(
                        'created_by',
                    ).order_by('created_at', 'id'),
                ),
            )
            .get(pk=ticket.pk)
        )
        ticket._prefetched_reads = [
            SupportTicketRead(ticket_id=ticket.pk, user_id=request.user.pk),
        ]
        ticket._message_count = ticket.messages.count()
        serializer = self.get_serializer(ticket)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        ticket = self.get_object()
        serializer = self.get_serializer(ticket, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        old_status = ticket.status
        serializer.save()
        if serializer.validated_data.get('status') != old_status:
            clear_support_ticket_read(ticket, ticket.created_by)
        ticket = self.get_queryset().get(pk=ticket.pk)
        ticket._prefetched_reads = list(
            SupportTicketRead.objects.filter(
                ticket_id=ticket.pk,
                user_id=request.user.pk,
            ),
        )
        out = SupportTicketSerializer(ticket, context=self.get_serializer_context())
        return Response(out.data)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        ticket = self.get_object()
        mark_support_ticket_read(ticket, request.user)
        ticket._prefetched_reads = [
            SupportTicketRead(ticket_id=ticket.pk, user_id=request.user.pk),
        ]
        serializer = SupportTicketSerializer(
            ticket,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='messages')
    def post_message(self, request, pk=None):
        from users.roles import feature_access_level_for_request

        if feature_access_level_for_request(
            request.user,
            'admin_support',
            safe_method=False,
        ) != 'write':
            raise PermissionDenied('Write access required to reply.')
        ticket = self.get_object()
        serializer = SupportTicketMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = create_support_ticket_message(
            ticket=ticket,
            body=serializer.validated_data['body'],
            author=request.user,
            is_staff=True,
        )
        return Response(
            SupportTicketMessageSerializer(
                message,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )
