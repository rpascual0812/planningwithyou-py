from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0029_bookingitem_company'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='bookingstatus',
            table='booking_statuses',
        ),
    ]
