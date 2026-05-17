import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_remove_account_price'),
        ('subscriptions', '0003_subscription_is_selectable'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ('reference_id', models.CharField(blank=True, default='', max_length=255)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('base_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('total_per_users', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('discount_code', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                (
                    'account',
                    models.ForeignKey(
                        db_column='account_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='account_subscriptions',
                        to='users.account',
                    ),
                ),
                (
                    'subscription',
                    models.ForeignKey(
                        db_column='subscription_id',
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='account_subscriptions',
                        to='subscriptions.subscription',
                    ),
                ),
            ],
            options={
                'db_table': 'account_subscriptions',
                'ordering': ['-start_date', '-id'],
            },
        ),
    ]
