import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0033_formtemplate_company'),
        ('companies', '0007_company_max_bookings_per_day'),
        ('users', '0016_remove_account_supplier_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookingPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_method', models.CharField(blank=True, default='', max_length=63)),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('tax', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('transaction_id', models.CharField(blank=True, default='', max_length=255)),
                ('transaction_status', models.CharField(blank=True, db_index=True, default='', max_length=63)),
                ('notes', models.TextField(blank=True, default='')),
                ('api_response', models.JSONField(blank=True, default=None, null=True)),
                ('transaction_date', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('account', models.ForeignKey(db_column='account_id', on_delete=django.db.models.deletion.CASCADE, related_name='+', to='users.account')),
                ('booking', models.ForeignKey(db_column='booking_id', on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='bookings.bookingitem')),
                ('company', models.ForeignKey(db_column='company_id', on_delete=django.db.models.deletion.PROTECT, related_name='booking_payments', to='companies.company')),
            ],
            options={
                'db_table': 'booking_payments',
                'ordering': ['-transaction_date', '-created_at'],
            },
        ),
    ]
