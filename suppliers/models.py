from django.conf import settings
from django.db import models


class SupplierTypeQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class SupplierTypeManager(models.Manager.from_queryset(SupplierTypeQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SupplierTypeAllManager(models.Manager.from_queryset(SupplierTypeQuerySet)):
    pass


class SupplierType(models.Model):
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SupplierTypeManager()
    all_objects = SupplierTypeAllManager()

    class Meta:
        db_table = 'supplier_types'
        ordering = ['name']

    def __str__(self):
        return self.name


class SupplierSetting(models.Model):
    is_active = models.BooleanField(default=True)
    supplier = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='supplier_id',
        related_name='supplier_settings_as_supplier',
    )
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='supplier_settings_as_account',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'supplier_settings'
        ordering = ['-updated_at', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['supplier', 'account'],
                name='supplier_settings_supplier_account_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.supplier_id} → {self.account_id}'


class TierQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class TierManager(models.Manager.from_queryset(TierQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class TierAllManager(models.Manager.from_queryset(TierQuerySet)):
    pass


class Tier(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='tiers',
    )
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='created_by_id',
        related_name='tiers_created',
    )

    objects = TierManager()
    all_objects = TierAllManager()

    class Meta:
        db_table = 'tiers'
        ordering = ['name']

    def __str__(self):
        return self.name


class SupplierSettingTier(models.Model):
    class AdjustmentType(models.TextChoices):
        PERCENT = 'percent', 'Percent'
        FIXED = 'fixed', 'Fixed amount'

    supplier_setting = models.ForeignKey(
        SupplierSetting,
        on_delete=models.CASCADE,
        db_column='supplier_setting_id',
        related_name='tiers',
    )
    tier = models.ForeignKey(
        Tier,
        on_delete=models.PROTECT,
        db_column='tier_id',
        related_name='supplier_setting_tiers',
    )
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    discount_type = models.CharField(
        max_length=20,
        choices=AdjustmentType.choices,
        default=AdjustmentType.PERCENT,
    )
    mark_up = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    mark_up_type = models.CharField(
        max_length=20,
        choices=AdjustmentType.choices,
        default=AdjustmentType.PERCENT,
    )
    price_override = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    tax = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'supplier_setting_tiers'
        ordering = ['tier__name', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['supplier_setting', 'tier'],
                name='supplier_setting_tiers_setting_tier_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.supplier_setting_id} / {self.tier_id}'
