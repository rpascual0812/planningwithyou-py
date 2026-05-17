import uuid

from django.db import models


class Subscription(models.Model):
    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'

    plan = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    subtitle = models.TextField(blank=True, default='')
    features = models.JSONField(default=list, blank=True)
    billing_cycle = models.CharField(
        max_length=20,
        choices=BillingCycle.choices,
    )
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_per_user = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    default_users = models.PositiveIntegerField(default=1)
    has_team_stepper = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_selectable = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'
        ordering = ['sort_order', 'plan']
        constraints = [
            models.UniqueConstraint(
                fields=['plan', 'billing_cycle'],
                name='subscriptions_plan_billing_cycle_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_billing_cycle_display()})'


class AccountSubscription(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='account_subscriptions',
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        db_column='subscription_id',
        related_name='account_subscriptions',
    )
    reference_id = models.CharField(max_length=255, blank=True, default='')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_per_users = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_code = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'account_subscriptions'
        ordering = ['-start_date', '-id']

    def __str__(self):
        return f'{self.account_id} → {self.subscription_id} ({self.uuid})'
