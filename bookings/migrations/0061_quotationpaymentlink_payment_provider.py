from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0060_quotationline_supplier_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='quotationpaymentlink',
            name='payment_provider',
            field=models.CharField(
                choices=[('paymongo', 'PayMongo'), ('xendit', 'Xendit')],
                db_index=True,
                default='paymongo',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='quotationpaymentlink',
            name='xendit_checkout_url',
            field=models.URLField(blank=True, default='', max_length=2048),
        ),
        migrations.AddField(
            model_name='quotationpaymentlink',
            name='xendit_payment_session_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
