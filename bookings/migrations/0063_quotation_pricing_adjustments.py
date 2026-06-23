from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0062_quotationpaymentlink_success_return_confirmed_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotation',
            name='discount_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='quotation',
            name='discount_type',
            field=models.CharField(blank=True, default='', max_length=16),
        ),
        migrations.AddField(
            model_name='quotation',
            name='total_override_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
            ),
        ),
    ]
