from datetime import datetime, time

from django.db import migrations, models
from django.utils import timezone


def _end_of_day(dt: datetime, tz) -> datetime:
    local = timezone.localtime(dt, tz)
    return timezone.make_aware(
        datetime.combine(local.date(), time(23, 59, 59, 999999)),
        tz,
    )


def widen_migrated_end_dates(apps, schema_editor):
    """Preserve inclusive end dates after date → timestamptz cast (midnight)."""
    Notification = apps.get_model('system_notifications', 'SystemNotification')
    tz = timezone.get_current_timezone()
    for row in Notification.objects.all():
        end = row.end_date
        if end is None:
            continue
        end_local = timezone.localtime(end, tz)
        if (
            end_local.hour == 0
            and end_local.minute == 0
            and end_local.second == 0
            and end_local.microsecond == 0
        ):
            Notification.objects.filter(pk=row.pk).update(
                end_date=_end_of_day(end, tz),
            )


class Migration(migrations.Migration):

    dependencies = [
        ('system_notifications', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemnotification',
            name='start_date',
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name='systemnotification',
            name='end_date',
            field=models.DateTimeField(),
        ),
        migrations.RunPython(widen_migrated_end_dates, migrations.RunPython.noop),
    ]
