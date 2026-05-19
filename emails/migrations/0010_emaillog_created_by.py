from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_created_by(apps, schema_editor):
    EmailLog = apps.get_model('emails', 'EmailLog')
    EmailLog.objects.filter(created_by_id__isnull=True).update(created_by_id=1)


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0009_emaillog_reply_to'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='emaillog',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                db_column='created_by',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='email_logs_created',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_created_by, migrations.RunPython.noop),
    ]
