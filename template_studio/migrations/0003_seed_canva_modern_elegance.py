from django.db import migrations


def seed_canva_modern_elegance(apps, schema_editor):
    from template_studio.canva_modern_elegance_document import MARKETPLACE_ENTRY

    InvitationTemplate = apps.get_model('template_studio', 'InvitationTemplate')
    item = MARKETPLACE_ENTRY
    existing = InvitationTemplate.objects.filter(
        slug=item['slug'],
        is_marketplace=True,
    ).first()
    if existing is not None:
        existing.title = item['title']
        existing.description = item['description']
        existing.document = item['document']
        existing.marketplace_preview_url = item['marketplace_preview_url']
        existing.is_published = True
        existing.is_deleted = False
        existing.save(
            update_fields=[
                'title',
                'description',
                'document',
                'marketplace_preview_url',
                'is_published',
                'is_deleted',
                'updated_at',
            ],
        )
        return
    InvitationTemplate.objects.create(
        title=item['title'],
        slug=item['slug'],
        category=item['category'],
        description=item['description'],
        document=item['document'],
        marketplace_preview_url=item['marketplace_preview_url'],
        is_marketplace=True,
        is_published=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('template_studio', '0002_seed_marketplace_templates'),
    ]

    operations = [
        migrations.RunPython(seed_canva_modern_elegance, migrations.RunPython.noop),
    ]
