from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('calendars', '0005_alter_calendar_repeat_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendar',
            name='location',
            field=models.TextField(blank=True, default=''),
        ),
    ]
