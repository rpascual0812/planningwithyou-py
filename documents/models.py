import os

from django.db import models


def document_upload_path(instance, filename):
    return f'documents/{filename}'


class Document(models.Model):
    file = models.FileField(upload_to=document_upload_path)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True, default='')
    size = models.PositiveBigIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'documents'
        ordering = ['-created_at']

    def __str__(self):
        return self.original_name

    @property
    def extension(self):
        _, ext = os.path.splitext(self.original_name)
        return ext.lower().lstrip('.')

    @property
    def is_image(self):
        return self.extension in {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico'}
