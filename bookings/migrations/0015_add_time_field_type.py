from django.db import migrations, models

FIELD_TYPE_CHOICES = [
    ('text', 'Text'),
    ('textarea', 'Text Area'),
    ('number', 'Number'),
    ('date', 'Date'),
    ('time', 'Time'),
    ('select', 'Dropdown'),
    ('checkbox', 'Checkbox'),
    ('email', 'Email'),
    ('phone', 'Phone'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0014_rename_booking_field_value_to_line_and_table'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bookingline',
            name='field_type',
            field=models.CharField(
                choices=FIELD_TYPE_CHOICES,
                default='text',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='formtemplatefield',
            name='field_type',
            field=models.CharField(
                choices=FIELD_TYPE_CHOICES,
                default='text',
                max_length=20,
            ),
        ),
    ]
