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
    """Single active subscription row per account (prepaid period + optional scheduled change)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Past due'
        UNPAID = 'unpaid', 'Unpaid'
        CANCELLED = 'cancelled', 'Cancelled'

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
    scheduled_subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='scheduled_account_subscriptions',
        db_column='scheduled_subscription_id',
    )
    scheduled_team_seats = models.PositiveIntegerField(null=True, blank=True)
    reference_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='PayMongo subscription id for paid plans.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    team_seats = models.PositiveIntegerField(default=1)
    start_date = models.DateField(help_text='Start of the current prepaid period.')
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text='End of prepaid period; null for lifetime Free.',
    )
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
        constraints = [
            models.UniqueConstraint(
                fields=['account'],
                condition=models.Q(deleted_at__isnull=True),
                name='account_subscriptions_one_per_account',
            ),
        ]

    def __str__(self):
        return f'{self.account_id} → {self.subscription.plan} ({self.status})'


class SubscriptionPayment(models.Model):
    """Recorded subscription charge (initial or recurring)."""

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='subscription_payments',
    )
    account_subscription = models.ForeignKey(
        AccountSubscription,
        on_delete=models.CASCADE,
        related_name='payments',
        db_column='account_subscription_id',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='PHP')
    paid_at = models.DateTimeField()
    paymongo_invoice_id = models.CharField(max_length=255, blank=True, default='')
    paymongo_payment_id = models.CharField(max_length=255, blank=True, default='')
    period_start = models.DateField()
    period_end = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subscription_payments'
        ordering = ['-paid_at', '-id']

    def __str__(self):
        return f'Payment {self.amount} ({self.account_id})'


class SubscriptionReceipt(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='subscription_receipts',
    )
    payment = models.OneToOneField(
        SubscriptionPayment,
        on_delete=models.CASCADE,
        related_name='receipt',
        db_column='subscription_payment_id',
    )
    receipt_number = models.CharField(max_length=32, unique=True)
    storage_key = models.CharField(max_length=512, blank=True, default='')
    receipt_url = models.URLField(max_length=1024, blank=True, default='')
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subscription_receipts'
        ordering = ['-created_at']

    def __str__(self):
        return self.receipt_number


class SubscriptionFailedPaymentNotice(models.Model):
    """Tracks failed subscription invoice emails (one per PayMongo invoice)."""

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='subscription_failed_payment_notices',
    )
    paymongo_invoice_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subscription_failed_payment_notices'
        ordering = ['-created_at']

    def __str__(self):
        return f'Failed payment notice {self.paymongo_invoice_id}'
