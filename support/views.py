from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import HasAccount

from .models import SupportTicket, SupportTicketMessage, SupportTicketRead
from .serializers import (
    SupportTicketCreateSerializer,
    SupportTicketDetailSerializer,
    SupportTicketMessageCreateSerializer,
    SupportTicketMessageSerializer,
    SupportTicketSerializer,
)
from .querysets import annotate_support_ticket_list, order_support_tickets_for_viewer
from .services import create_support_ticket_message, mark_support_ticket_read


class SupportTicketViewSet(viewsets.ModelViewSet):
    """Current user's support tickets."""

    permission_classes = [IsAuthenticated, HasAccount]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    class Pagination(PageNumberPagination):
        page_size = 10

    pagination_class = Pagination

    def get_queryset(self):
        user = self.request.user
        qs = SupportTicket.objects.filter(created_by_id=user.pk).select_related(
            'created_by',
        )
        qs = annotate_support_ticket_list(qs)
        return order_support_tickets_for_viewer(qs, user)

    def get_serializer_class(self):
        if self.action == 'create':
            return SupportTicketCreateSerializer
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
        page = self.paginate_queryset(queryset)
        if page is not None:
            tickets = self._attach_read_state(page, request.user)
            serializer = self.get_serializer(tickets, many=True)
            return self.get_paginated_response(serializer.data)
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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = SupportTicket.objects.create(
            title=serializer.validated_data['title'].strip(),
            created_by=request.user,
        )
        create_support_ticket_message(
            ticket=ticket,
            body=serializer.validated_data['message'],
            author=request.user,
            is_staff=False,
        )
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
        out = SupportTicketDetailSerializer(ticket, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        if instance.created_by_id != self.request.user.pk:
            raise PermissionDenied('Only the ticket creator can delete it.')
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at'])

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
        ticket = self.get_object()
        if ticket.created_by_id != request.user.pk:
            raise PermissionDenied('Only the ticket creator can reply here.')
        serializer = SupportTicketMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = create_support_ticket_message(
            ticket=ticket,
            body=serializer.validated_data['body'],
            author=request.user,
            is_staff=False,
        )
        return Response(
            SupportTicketMessageSerializer(
                message,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )
