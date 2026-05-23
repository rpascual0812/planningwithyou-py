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
    key = models.TextField(
        help_text='PayMongo secret API key (sk_live_… / sk_test_…).',
    )
    secret = models.TextField(
        blank=True,
        default='',
        help_text='PayMongo webhook signing secret.',
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
