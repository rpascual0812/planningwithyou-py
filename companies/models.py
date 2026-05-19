from django.conf import settings
from django.db import models


class CompanyQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class CompanyManager(models.Manager.from_queryset(CompanyQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class CompanyAllManager(models.Manager.from_queryset(CompanyQuerySet)):
    pass


class Company(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='companies',
    )
    name = models.CharField(max_length=255)
    timezone = models.CharField(max_length=63, blank=True, default='')
    website = models.URLField(max_length=512, blank=True, default='')
    is_active = models.BooleanField(default=True)
    is_main = models.BooleanField(default=False)
    logo = models.CharField(
        max_length=512,
        blank=True,
        default='',
        help_text='Secured API URL for the company logo download route.',
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='companies_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = CompanyManager()
    all_objects = CompanyAllManager()

    class Meta:
        db_table = 'companies'
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['account'],
                condition=models.Q(is_main=True),
                name='companies_one_main_per_account',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.is_main and self.account_id:
            qs = Company.all_objects.filter(
                account_id=self.account_id,
                is_main=True,
            )
            if self.pk is not None:
                qs = qs.exclude(pk=self.pk)
            qs.update(is_main=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
