from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0038_rename_booking_total_tax_to_required_downpayment'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingline',
            name='required_downpayment',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
            ),
        ),
    ]
