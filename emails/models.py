from django.conf import settings
from django.db import models


class EmailLog(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    to = models.JSONField(
        default=list,
        help_text='List of recipient email addresses.',
    )
    cc = models.JSONField(
        default=list,
        blank=True,
        help_text='List of CC email addresses.',
    )
    bcc = models.JSONField(
        default=list,
        blank=True,
        help_text='List of BCC email addresses.',
    )
    email_from = models.EmailField(
        help_text='Sender email address used for this message.',
    )
    reply_to = models.EmailField(
        blank=True,
        default='',
        help_text='Optional reply-to address (single recipient).',
    )
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True, default='')
    attachments = models.JSONField(
        default=list,
        blank=True,
        help_text='List of attachment URLs.',
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    error = models.TextField(blank=True, default='')
    attempts = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'email_logs'
        ordering = ['-created_at']

    def __str__(self):
        recipients = ', '.join(self.to[:3])
        if len(self.to) > 3:
            recipients += f' (+{len(self.to) - 3})'
        return f'{self.subject} → {recipients} [{self.status}]'


class EmailTemplate(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    class TemplateType(models.TextChoices):
        USERS = 'users', 'Users'
        BOOKINGS = 'bookings', 'Bookings'

    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True, default='')
    subject = models.CharField(max_length=255, blank=True, default='')
    body = models.TextField(blank=True, default='')
    template_type = models.CharField(
        max_length=32,
        choices=TemplateType.choices,
        db_index=True,
        db_column='type',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'email_templates'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.template_type})'
