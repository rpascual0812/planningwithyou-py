from django.contrib.auth import get_user_model

from users.roles import feature_access_level_for_request

from .models import SupportTicket, SupportTicketMessage, SupportTicketRead

User = get_user_model()


def user_display_name(user: User) -> str:
    full = f'{user.first_name or ""} {user.last_name or ""}'.strip()
    return full or user.username or user.email or ''


def user_is_support_staff(user: User) -> bool:
    if not user.is_authenticated:
        return False
    return feature_access_level_for_request(user, 'admin_support', safe_method=True) in (
        'read',
        'write',
    )


def mark_support_ticket_read(ticket: SupportTicket, user: User) -> None:
    SupportTicketRead.objects.get_or_create(ticket=ticket, user=user)


def clear_support_ticket_read(ticket: SupportTicket, user: User) -> None:
    SupportTicketRead.objects.filter(ticket=ticket, user=user).delete()


def mark_unread_for_other_participants(ticket: SupportTicket, sender: User) -> None:
    SupportTicketRead.objects.filter(ticket=ticket).exclude(user_id=sender.pk).delete()


def reopen_ticket_if_needed(ticket: SupportTicket) -> None:
    if ticket.status in (SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED):
        ticket.status = SupportTicket.Status.IN_PROGRESS
        ticket.save(update_fields=['status'])


def create_support_ticket_message(
    *,
    ticket: SupportTicket,
    body: str,
    author: User,
    is_staff: bool,
) -> SupportTicketMessage:
    message = SupportTicketMessage.objects.create(
        ticket=ticket,
        body=body,
        created_by=author,
        is_staff=is_staff,
    )
    mark_support_ticket_read(ticket, author)
    mark_unread_for_other_participants(ticket, author)
    if is_staff:
        reopen_ticket_if_needed(ticket)
    elif ticket.status == SupportTicket.Status.CLOSED:
        ticket.status = SupportTicket.Status.OPEN
        ticket.save(update_fields=['status'])
    return message
