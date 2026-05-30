from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def consolidate_account_subscriptions(apps, schema_editor):
    AccountSubscription = apps.get_model('subscriptions', 'AccountSubscription')
    now = timezone.now()
    account_ids = (
        AccountSubscription.objects.filter(deleted_at__isnull=True)
        .values_list('account_id', flat=True)
        .distinct()
    )
    status_rank = {
        'active': 0,
        'pending': 1,
        'past_due': 2,
        'unpaid': 3,
        'cancelled': 4,
    }
    for account_id in account_ids:
        rows = list(
            AccountSubscription.objects.filter(
                account_id=account_id,
                deleted_at__isnull=True,
            ).order_by('-start_date', '-id'),
        )
        if len(rows) <= 1:
            continue

        def sort_key(row):
            return (
                status_rank.get(row.status, 99),
                -(row.start_date.toordinal() if row.start_date else 0),
                -row.id,
            )

        rows.sort(key=sort_key)
        keep = rows[0]
        for row in rows[1:]:
            row.status = 'cancelled'
            row.deleted_at = now
            row.save(update_fields=['status', 'deleted_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0005_accountsubscription_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountsubscription',
            name='scheduled_subscription',
            field=models.ForeignKey(
                blank=True,
                db_column='scheduled_subscription_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='scheduled_account_subscriptions',
                to='subscriptions.subscription',
            ),
        ),
        migrations.AddField(
            model_name='accountsubscription',
            name='scheduled_team_seats',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(
            consolidate_account_subscriptions,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='accountsubscription',
            constraint=models.UniqueConstraint(
                condition=models.Q(('deleted_at__isnull', True)),
                fields=('account',),
                name='account_subscriptions_one_per_account',
            ),
        ),
        migrations.CreateModel(
            name='SubscriptionPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(default='PHP', max_length=3)),
                ('paid_at', models.DateTimeField()),
                ('paymongo_invoice_id', models.CharField(blank=True, default='', max_length=255)),
                ('paymongo_payment_id', models.CharField(blank=True, default='', max_length=255)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField(blank=True, null=True)),
                ('description', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'account',
                    models.ForeignKey(
                        db_column='account_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='subscription_payments',
                        to='users.account',
                    ),
                ),
                (
                    'account_subscription',
                    models.ForeignKey(
                        db_column='account_subscription_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='payments',
                        to='subscriptions.accountsubscription',
                    ),
                ),
            ],
            options={
                'db_table': 'subscription_payments',
                'ordering': ['-paid_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='SubscriptionReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('receipt_number', models.CharField(max_length=32, unique=True)),
                ('storage_key', models.CharField(blank=True, default='', max_length=512)),
                ('receipt_url', models.URLField(blank=True, default='', max_length=1024)),
                ('emailed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'account',
                    models.ForeignKey(
                        db_column='account_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='subscription_receipts',
                        to='users.account',
                    ),
                ),
                (
                    'payment',
                    models.OneToOneField(
                        db_column='subscription_payment_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='receipt',
                        to='subscriptions.subscriptionpayment',
                    ),
                ),
            ],
            options={
                'db_table': 'subscription_receipts',
                'ordering': ['-created_at'],
            },
        ),
    ]
