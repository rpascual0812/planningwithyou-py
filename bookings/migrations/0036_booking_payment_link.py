import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0035_booking_total_amount_tax'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('companies', '0007_company_max_bookings_per_day'),
        ('users', '0012_alter_account_logo_charfield'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookingPaymentLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public_token', models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ('paymongo_checkout_session_id', models.CharField(blank=True, default='', max_length=255)),
                ('paymongo_checkout_url', models.URLField(blank=True, default='', max_length=2048)),
                ('base_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('platform_fee', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('processing_fee_estimate', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('charge_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='PHP', max_length=3)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('expired', 'Expired'), ('cancelled', 'Cancelled')], db_index=True, default='pending', max_length=20)),
                ('expires_at', models.DateTimeField()),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(db_column='account_id', on_delete=django.db.models.deletion.CASCADE, related_name='+', to='users.account')),
                ('booking', models.ForeignKey(db_column='booking_id', on_delete=django.db.models.deletion.CASCADE, related_name='payment_links', to='bookings.bookingitem')),
                ('company', models.ForeignKey(db_column='company_id', on_delete=django.db.models.deletion.PROTECT, related_name='booking_payment_links', to='companies.company')),
                ('created_by', models.ForeignKey(blank=True, db_column='created_by', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='booking_payment_links_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'booking_payment_links',
                'ordering': ['-created_at'],
            },
        ),
    ]
