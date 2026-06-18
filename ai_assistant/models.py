from django.conf import settings
from django.db import models


class AiRequestLog(models.Model):
    class Action(models.TextChoices):
        SUMMARIZE = 'summarize', 'Summarize quotation'
        DRAFT_EMAIL = 'draft_email', 'Draft quotation email'

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='+',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        db_column='user_id',
    )
    quotation = models.ForeignKey(
        'bookings.Quotation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        db_column='quotation_id',
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    model = models.CharField(max_length=64, blank=True, default='')
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_request_logs'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.action} #{self.pk}'
