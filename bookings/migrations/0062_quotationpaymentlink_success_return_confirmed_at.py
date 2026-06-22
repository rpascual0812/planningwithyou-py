from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0061_quotationpaymentlink_payment_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotationpaymentlink',
            name='success_return_confirmed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the customer success return URL was first consumed.',
                null=True,
            ),
        ),
    ]
