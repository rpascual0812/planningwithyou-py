from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0007_alter_accountsubscription_end_date_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionFailedPaymentNotice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('paymongo_invoice_id', models.CharField(max_length=255, unique=True)),
                ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('emailed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'account',
                    models.ForeignKey(
                        db_column='account_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='subscription_failed_payment_notices',
                        to='users.account',
                    ),
                ),
            ],
            options={
                'db_table': 'subscription_failed_payment_notices',
                'ordering': ['-created_at'],
            },
        ),
    ]
