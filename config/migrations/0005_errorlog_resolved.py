import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('config', '0004_errorlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='errorlog',
            name='resolved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='errorlog',
            name='resolved_by',
            field=models.ForeignKey(
                blank=True,
                db_column='resolved_by_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='resolved_error_logs',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
