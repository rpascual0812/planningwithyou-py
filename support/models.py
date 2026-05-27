from django.conf import settings
from django.db import models


class SupportTicketQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class SupportTicketManager(models.Manager.from_queryset(SupportTicketQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SupportTicketAllManager(models.Manager.from_queryset(SupportTicketQuerySet)):
    pass


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In progress'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'

    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.OPEN,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_tickets_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SupportTicketManager()
    all_objects = SupportTicketAllManager()

    class Meta:
        db_table = 'support_tickets'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.title


class SupportTicketMessage(models.Model):
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='messages',
        db_column='ticket_id',
    )
    body = models.TextField()
    is_staff = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_ticket_messages_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_ticket_messages'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'ticket={self.ticket_id} message={self.pk}'


class SupportTicketRead(models.Model):
    """Per-user read state for a support ticket."""

    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='reads',
        db_column='ticket_id',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_ticket_reads',
        db_column='user_id',
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_ticket_reads'
        constraints = [
            models.UniqueConstraint(
                fields=['ticket', 'user'],
                name='support_ticket_reads_ticket_user_uniq',
            ),
        ]

    def __str__(self):
        return f'ticket={self.ticket_id} user={self.user_id}'
