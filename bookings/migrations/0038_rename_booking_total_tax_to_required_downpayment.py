from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0037_alter_bookingpaymentlink_created_by_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='bookingitem',
            old_name='total_tax',
            new_name='required_downpayment_amount',
        ),
    ]
