from django.db import migrations, models


def backfill_resource_fields(apps, schema_editor):
    History = apps.get_model('bookings', 'History')
    for row in History.objects.all().iterator():
        if row.booking_id and not row.resource_id:
            row.resource_type = 'booking'
            row.resource_id = row.booking_id
            row.save(update_fields=['resource_type', 'resource_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0044_alter_history_booking_set_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='history',
            name='resource_type',
            field=models.CharField(
                choices=[
                    ('booking', 'Booking'),
                    ('account', 'Account'),
                    ('company', 'Company'),
                    ('user', 'User'),
                    ('contact', 'Contact'),
                    ('supplier_setting', 'Supplier setting'),
                    ('booking_status', 'Booking status'),
                    ('email_template', 'Email template'),
                ],
                default='booking',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='history',
            name='resource_id',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_resource_fields, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='history',
            name='entity_type',
            field=models.CharField(max_length=32),
        ),
        migrations.AddIndex(
            model_name='history',
            index=models.Index(
                fields=['resource_type', 'resource_id', '-created_at'],
                name='history_resource_created_idx',
            ),
        ),
    ]
