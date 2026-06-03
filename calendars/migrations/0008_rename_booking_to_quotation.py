from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0056_rename_bookings_to_quotations'),
        ('calendars', '0007_google_calendar_integration'),
    ]

    operations = [
        migrations.RunSQL(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'calendar' AND column_name = 'booking_id'
                ) THEN
                    ALTER TABLE calendar RENAME COLUMN booking_id TO quotation_id;
                END IF;
            END $$;
            """,
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'calendar' AND column_name = 'quotation_id'
                ) THEN
                    ALTER TABLE calendar RENAME COLUMN quotation_id TO booking_id;
                END IF;
            END $$;
            """,
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameField(
                    model_name='calendar',
                    old_name='booking',
                    new_name='quotation',
                ),
            ],
        ),
    ]
