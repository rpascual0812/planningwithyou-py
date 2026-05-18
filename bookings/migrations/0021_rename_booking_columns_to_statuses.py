from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0020_remove_bookingitem_form_template'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='BookingColumn',
            new_name='BookingStatus',
        ),
        migrations.AlterModelTable(
            name='bookingstatus',
            table='statuses',
        ),
        migrations.RenameField(
            model_name='bookingitem',
            old_name='column',
            new_name='status',
        ),
    ]
