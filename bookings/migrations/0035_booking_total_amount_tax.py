from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0034_booking_payment'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingitem',
            name='total_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='bookingitem',
            name='total_tax',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
