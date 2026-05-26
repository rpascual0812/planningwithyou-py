from django.db import migrations


def drop_history_booking_id_not_null(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_name = 'history' AND column_name = 'booking_id'
            """,
        )
        row = cursor.fetchone()
        if row and row[0] == 'NO':
            cursor.execute(
                'ALTER TABLE history ALTER COLUMN booking_id DROP NOT NULL',
            )


class Migration(migrations.Migration):

    dependencies = [
        (
            'bookings',
            '0046_rename_history_resource_created_idx_history_resourc_a2be40_idx_and_more',
        ),
    ]

    operations = [
        migrations.RunPython(
            drop_history_booking_id_not_null,
            migrations.RunPython.noop,
        ),
    ]
