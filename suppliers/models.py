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
