import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0043_history'),
    ]

    operations = [
        migrations.AlterField(
            model_name='history',
            name='booking',
            field=models.ForeignKey(
                blank=True,
                db_column='booking_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='history_entries',
                to='bookings.bookingitem',
            ),
        ),
    ]
