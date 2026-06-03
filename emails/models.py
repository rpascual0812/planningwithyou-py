from django.conf import settings
from django.db import models


class EmailLog(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='email_logs',
        db_column='company_id',
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
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='email_templates',
        db_column='company_id',
    )
    class TemplateType(models.TextChoices):
        USERS = 'users', 'Users'
        BOOKINGS = 'bookings', 'Bookings'
        CALENDAR = 'calendar', 'Calendar'

    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True, default='')
    cc = models.JSONField(
        default=list,
        blank=True,
        help_text='Default CC email addresses for messages using this template.',
    )
    bcc = models.JSONField(
        default=list,
        blank=True,
        help_text='Default BCC email addresses for messages using this template.',
    )
    subject = models.CharField(max_length=255, blank=True, default='')
    body = models.TextField(blank=True, default='')
    template_type = models.CharField(
        max_length=32,
        choices=TemplateType.choices,
        db_index=True,
        db_column='type',
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text='System-seeded templates; not deletable from the app.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'email_templates'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.template_type})'


class GmailIntegration(models.Model):
    """OAuth-connected Gmail used to send email for a company."""

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='gmail_integrations',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='gmail_integrations',
    )
    google_email = models.EmailField(max_length=255, blank=True, default='')
    access_token_encrypted = models.TextField(blank=True, default='')
    refresh_token_encrypted = models.TextField(blank=True, default='')
    token_expiry = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gmail_integrations_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gmail_integrations'
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'company'],
                name='gmail_integrations_one_per_company',
            ),
        ]

    def __str__(self):
        return f'Gmail {self.google_email or "—"} company={self.company_id}'
