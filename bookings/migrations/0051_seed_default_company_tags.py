from django.db import migrations

# Keep in sync with users.registration.DEFAULT_COMPANY_TAGS
DEFAULT_COMPANY_TAGS = ('new', 'confirmed', 'cancelled', 'completed', 'done')


def seed_default_company_tags(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    Tag = apps.get_model('bookings', 'Tag')

    for company in Company.objects.filter(deleted_at__isnull=True).iterator():
        account_id = company.account_id
        company_id = company.id
        for tag_name in DEFAULT_COMPANY_TAGS:
            exists = Tag.objects.filter(
                account_id=account_id,
                company_id=company_id,
                tag__iexact=tag_name,
            ).exists()
            if not exists:
                Tag.objects.create(
                    account_id=account_id,
                    company_id=company_id,
                    tag=tag_name,
                )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0050_tag_bookingstatus_tags'),
        ('companies', '0010_company_contact_email'),
    ]

    operations = [
        migrations.RunPython(seed_default_company_tags, noop_reverse),
    ]
