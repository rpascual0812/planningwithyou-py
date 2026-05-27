from django.db.models import Count, Exists, F, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce

from .models import SupportTicketMessage, SupportTicketRead


def _latest_message_subquery():
    return SupportTicketMessage.objects.filter(
        ticket_id=OuterRef('pk'),
    ).order_by('-created_at', '-id')


def annotate_support_ticket_list(queryset):
    latest = _latest_message_subquery()
    return queryset.annotate(
        _message_count=Count('messages', distinct=True),
        _last_message_id=Subquery(latest.values('pk')[:1]),
        _last_message_at=Coalesce(
            Subquery(latest.values('created_at')[:1]),
            F('created_at'),
        ),
    )


def filter_admin_support_tickets(queryset, request):
    qs = queryset
    status = request.query_params.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)
    search = request.query_params.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(created_by__username__icontains=search)
            | Q(created_by__email__icontains=search)
            | Q(created_by__first_name__icontains=search)
            | Q(created_by__last_name__icontains=search)
            | Q(messages__body__icontains=search),
        ).distinct()
    return qs


def order_support_tickets_for_viewer(queryset, user):
    """Unread first, then by latest message activity (newest first)."""
    read_exists = SupportTicketRead.objects.filter(
        ticket_id=OuterRef('pk'),
        user_id=user.pk,
    )
    return queryset.annotate(_viewer_has_read=Exists(read_exists)).order_by(
        '_viewer_has_read',
        '-_last_message_at',
        '-id',
    )
