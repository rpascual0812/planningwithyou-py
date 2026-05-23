from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0041_alter_bookingpayment_base_amount_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingpayment',
            name='payout_sent_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the platform marked this payment as paid out to the company.',
                null=True,
            ),
        ),
    ]
