from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0047_drop_history_booking_id_not_null'),
    ]

    operations = [
        migrations.AlterField(
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
                    ('form_template', 'Form template'),
                ],
                default='booking',
                max_length=32,
            ),
        ),
    ]
