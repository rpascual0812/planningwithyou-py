from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0013_alter_bookingcolumn_account_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='BookingFieldValue',
            new_name='BookingLine',
        ),
        migrations.AlterModelTable(
            name='BookingLine',
            table='booking_items',
        ),
    ]
