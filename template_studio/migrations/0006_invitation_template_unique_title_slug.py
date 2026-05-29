"""Enforce unique slug (global) and title (per company) on active invitation templates."""

from django.db import migrations, models
from django.db.models import Count
from django.db.models.functions import Lower
from django.utils.text import slugify


def _dedupe_slugs(apps, schema_editor):
    InvitationTemplate = apps.get_model('template_studio', 'InvitationTemplate')
    dupes = (
        InvitationTemplate.objects.filter(is_deleted=False)
        .values('slug')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )
    for row in dupes:
        slug = row['slug']
        templates = list(
            InvitationTemplate.objects.filter(is_deleted=False, slug=slug).order_by('id'),
        )
        for idx, tpl in enumerate(templates[1:], start=2):
            base = slugify(slug)[:100] or 'invitation'
            tpl.slug = f'{base}-{idx}'[:120]
            tpl.save(update_fields=['slug', 'updated_at'])


def _dedupe_titles(apps, schema_editor):
    InvitationTemplate = apps.get_model('template_studio', 'InvitationTemplate')
    qs = (
        InvitationTemplate.objects.filter(is_deleted=False, is_marketplace=False)
        .exclude(company_id__isnull=True)
        .annotate(title_lower=Lower('title'))
        .values('company_id', 'title_lower')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )
    for row in qs:
        company_id = row['company_id']
        title_lower = row['title_lower']
        templates = list(
            InvitationTemplate.objects.filter(
                is_deleted=False,
                is_marketplace=False,
                company_id=company_id,
                title__iexact=title_lower,
            ).order_by('id'),
        )
        base_title = templates[0].title
        for idx, tpl in enumerate(templates[1:], start=2):
            suffix = f' ({idx})'
            tpl.title = f'{base_title[: 255 - len(suffix)]}{suffix}'
            tpl.save(update_fields=['title', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('template_studio', '0005_invitation_rsvp'),
    ]

    operations = [
        migrations.RunPython(_dedupe_slugs, migrations.RunPython.noop),
        migrations.RunPython(_dedupe_titles, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='invitationtemplate',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_deleted', False), ('is_marketplace', False)),
                fields=('company', 'title'),
                name='invitation_templates_company_title_uniq',
            ),
        ),
        migrations.AddConstraint(
            model_name='invitationtemplate',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_deleted', False)),
                fields=('slug',),
                name='invitation_templates_slug_uniq',
            ),
        ),
    ]
