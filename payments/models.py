from django.conf import settings
from django.db import models


class PaymentIntegrationQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class PaymentIntegrationManager(models.Manager.from_queryset(PaymentIntegrationQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class PaymentIntegrationAllManager(models.Manager.from_queryset(PaymentIntegrationQuerySet)):
    pass


class PaymentIntegration(models.Model):
    class PaymentGateway(models.TextChoices):
        PAYMONGO = 'paymongo', 'PayMongo'

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='payment_integrations',
    )
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='payment_integrations',
    )
    payment_gateway = models.CharField(
        max_length=63,
        choices=PaymentGateway.choices,
    )
    paymongo_account_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='PayMongo linked child account id (org_…).',
    )
    activation_status = models.CharField(
        max_length=63,
        blank=True,
        default='not_started',
        help_text='PayMongo child account activation_status.',
    )
    identity_verification_status = models.CharField(
        max_length=63,
        blank=True,
        default='',
        help_text='PayMongo identity_verification_status for the representative.',
    )
    identity_verification_url = models.URLField(
        max_length=2048,
        blank=True,
        default='',
        help_text='Hosted URL for the representative to complete PayMongo KYC.',
    )
    api_response = models.JSONField(null=True, blank=True, default=None)
    key = models.TextField(
        blank=True,
        default='',
        help_text='Deprecated: use PayMongo Platforms child account instead.',
    )
    secret = models.TextField(
        blank=True,
        default='',
        help_text='Deprecated: platform webhook secret is used.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='created_by',
        related_name='payment_integrations_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = PaymentIntegrationManager()
    all_objects = PaymentIntegrationAllManager()

    class Meta:
        db_table = 'payment_integrations'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'payment_gateway'],
                condition=models.Q(deleted_at__isnull=True),
                name='payment_integrations_one_gateway_per_company',
            ),
        ]

    def __str__(self):
        return f'{self.payment_gateway} company={self.company_id}'


class WebhookLog(models.Model):
    source = models.CharField(
        max_length=127,
        help_text='Webhook origin (e.g. paymongo).',
    )
    payload = models.JSONField(
        help_text='Full webhook request body as received.',
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When business logic finished processing this payload.',
    )
    handled = models.BooleanField(
        null=True,
        blank=True,
        help_text='Whether any handler applied this webhook to app state.',
    )
    error_message = models.TextField(
        blank=True,
        default='',
        help_text='Validation or processing error, if any.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'webhook_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.source} @ {self.created_at:%Y-%m-%d %H:%M:%S}'
