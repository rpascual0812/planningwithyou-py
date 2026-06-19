from django.db import migrations
from django.utils import timezone


def backfill_google_calendar_integration_created_at(apps, schema_editor):
    GoogleCalendarIntegration = apps.get_model('calendars', 'GoogleCalendarIntegration')
    for integration in GoogleCalendarIntegration.objects.filter(
        created_at__isnull=True,
    ).iterator():
        stamp = integration.updated_at or timezone.now()
        GoogleCalendarIntegration.objects.filter(pk=integration.pk).update(
            created_at=stamp,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('calendars', '0009_alter_calendar_quotation'),
    ]

    operations = [
        migrations.RunPython(
            backfill_google_calendar_integration_created_at,
            migrations.RunPython.noop,
        ),
    ]
