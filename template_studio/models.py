import os
import uuid

from django.conf import settings
from django.db import models


def template_asset_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.bin'
    account_id = getattr(instance, 'account_id', None) or 'unknown'
    return f'template_studio/{account_id}/{instance.uuid.hex}{ext}'


class TemplateAsset(models.Model):
    """Image (or other) file for template studio designs — stored in S3/local media."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='template_assets',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='template_assets',
    )
    file = models.FileField(upload_to=template_asset_upload_path)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True, default='')
    size = models.PositiveBigIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='template_assets',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'template_studio_assets'
        ordering = ['-created_at']

    def __str__(self):
        return self.original_name


class InvitationTemplate(models.Model):
    """Wedding invitation website template (editor JSON + publish metadata)."""

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='account_id',
        related_name='invitation_templates',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='company_id',
        related_name='invitation_templates',
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120)
    category = models.CharField(max_length=50, default='wedding')
    description = models.TextField(blank=True, default='')
    document = models.JSONField(default=dict)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    is_marketplace = models.BooleanField(
        default=False,
        help_text='System catalog template visible to all tenants.',
    )
    marketplace_preview_url = models.URLField(blank=True, default='')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_invitation_templates',
        db_column='created_by_id',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invitation_templates'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class InvitationRsvp(models.Model):
    """Guest RSVP submission for a published invitation template."""

    invitation_template = models.ForeignKey(
        InvitationTemplate,
        on_delete=models.CASCADE,
        related_name='rsvps',
        db_column='invitation_template_id',
    )
    element_id = models.CharField(
        max_length=64,
        help_text='Canvas element id of the RSVP widget in the template document.',
    )
    fields_data = models.JSONField(
        default=dict,
        help_text='Dynamic field values keyed by field id from the RSVP form config.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invitation_rsvps'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invitation_template', 'element_id']),
        ]

    def __str__(self):
        return f'RSVP for {self.invitation_template_id} ({self.element_id})'
