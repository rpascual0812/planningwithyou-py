from django.db import models

from .constants import LEGAL_DOCUMENT_NAMES


class SystemSetting(models.Model):
    """Platform-wide key/value settings (``system`` table)."""

    name = models.TextField(unique=True)
    value = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'system'
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def legal_documents_queryset(cls):
        return cls.objects.filter(name__in=LEGAL_DOCUMENT_NAMES)
