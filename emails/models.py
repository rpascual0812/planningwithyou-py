from django.db import models


class EmailLog(models.Model):
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
    subject = models.CharField(max_length=255)
    body_html = models.TextField(blank=True, default='')
    body_text = models.TextField(blank=True, default='')
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
