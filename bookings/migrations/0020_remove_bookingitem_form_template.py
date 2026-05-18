from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0019_alter_bookingline_booking_group_cascade'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='bookingitem',
            name='form_template',
        ),
    ]
