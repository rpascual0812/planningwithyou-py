from django.db import migrations
from django.utils import timezone


def backfill_gmail_integration_created_at(apps, schema_editor):
    GmailIntegration = apps.get_model('emails', 'GmailIntegration')
    for integration in GmailIntegration.objects.filter(created_at__isnull=True).iterator():
        stamp = integration.updated_at or timezone.now()
        GmailIntegration.objects.filter(pk=integration.pk).update(created_at=stamp)


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0026_seed_quotation_status_email_templates'),
    ]

    operations = [
        migrations.RunPython(
            backfill_gmail_integration_created_at,
            migrations.RunPython.noop,
        ),
    ]