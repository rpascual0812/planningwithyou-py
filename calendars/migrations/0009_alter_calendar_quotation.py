# Sync FK target after 0008 renamed booking -> quotation (column already quotation_id).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0057_remove_quotation_bookings_account_unique_id_uniq_and_more'),
        ('calendars', '0008_rename_booking_to_quotation'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='calendar',
                    name='quotation',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='quotation_id',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='calendar_events',
                        to='bookings.quotation',
                    ),
                ),
            ],
        ),
    ]
