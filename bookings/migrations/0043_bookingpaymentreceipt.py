from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('bookings', '0042_bookingpayment_payout_sent_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookingPaymentReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('receipt_url', models.TextField(blank=True, default='')),
                ('storage_key', models.TextField(blank=True, default='')),
                ('emailed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(db_column='account_id', on_delete=django.db.models.deletion.CASCADE, related_name='+', to='users.account')),
                ('booking', models.ForeignKey(db_column='booking_id', on_delete=django.db.models.deletion.CASCADE, related_name='payment_receipts', to='bookings.bookingitem')),
                ('booking_payment', models.OneToOneField(db_column='booking_payment_id', on_delete=django.db.models.deletion.CASCADE, related_name='receipt', to='bookings.bookingpayment')),
                ('company', models.ForeignKey(db_column='company_id', on_delete=django.db.models.deletion.PROTECT, related_name='booking_payment_receipts', to='companies.company')),
            ],
            options={
                'db_table': 'booking_payment_receipts',
                'ordering': ['-created_at'],
            },
        ),
    ]
