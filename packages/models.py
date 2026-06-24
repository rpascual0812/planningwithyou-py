from django.conf import settings
from django.db import models


class PackagePriceQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class PackagePriceManager(models.Manager.from_queryset(PackagePriceQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class PackagePriceAllManager(models.Manager.from_queryset(PackagePriceQuerySet)):
    pass


class PackagePrice(models.Model):
    package_version = models.ForeignKey(
        'PackageVersion',
        on_delete=models.PROTECT,
        db_column='package_version_id',
        related_name='package_prices',
    )
    package = models.ForeignKey(
        'suppliers.Package',
        on_delete=models.PROTECT,
        db_column='package_id',
        related_name='package_prices',
    )
    description = models.TextField(blank=True, default='')
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    required_downpayment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='package_prices',
    )
    is_active = models.BooleanField(default=True)
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='package_prices',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='created_by',
        related_name='package_prices_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = PackagePriceManager()
    all_objects = PackagePriceAllManager()

    class Meta:
        db_table = 'package_prices'
        ordering = ['package_id', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'package', 'package_version'],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name='package_prices_one_active_per_company_package_version',
            ),
        ]

    def __str__(self):
        if self.package_id and getattr(self, 'package', None) is not None:
            return self.package.name
        return f'Package price {self.id}'


class PackageItemQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class PackageItemManager(models.Manager.from_queryset(PackageItemQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class PackageItemAllManager(models.Manager.from_queryset(PackageItemQuerySet)):
    pass


class PackageItem(models.Model):
    package_price = models.ForeignKey(
        PackagePrice,
        on_delete=models.CASCADE,
        db_column='package_price_id',
        related_name='items',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='parent_id',
        related_name='children',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=0)
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='package_items',
    )
    is_active = models.BooleanField(default=True)
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='package_items',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='created_by',
        related_name='package_items_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = PackageItemManager()
    all_objects = PackageItemAllManager()

    class Meta:
        db_table = 'package_items'
        ordering = ['sort_order', 'title', 'id']

    def __str__(self):
        return self.title


class PackageVersionQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class PackageVersionManager(models.Manager.from_queryset(PackageVersionQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class PackageVersionAllManager(models.Manager.from_queryset(PackageVersionQuerySet)):
    pass


class PackageVersion(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    effectivity_date = models.DateTimeField(null=True, blank=True, db_column='effectivity_date')
    is_active = models.BooleanField(default=True)
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='package_versions',
    )
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='package_versions',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='created_by',
        related_name='package_versions_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = PackageVersionManager()
    all_objects = PackageVersionAllManager()

    class Meta:
        db_table = 'package_versions'
        ordering = ['title', 'id']

    def __str__(self):
        return self.title
