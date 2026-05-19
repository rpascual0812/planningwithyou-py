from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0030_rename_statuses_table'),
        ('calendars', '0002_calendar'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendar',
            name='booking',
            field=models.ForeignKey(
                blank=True,
                db_column='booking_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='calendar_events',
                to='bookings.bookingitem',
            ),
        ),
    ]
