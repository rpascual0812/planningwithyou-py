import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('companies', '0004_company_kyb_verification'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_gateway', models.CharField(choices=[('paymongo', 'PayMongo')], max_length=63)),
                ('key', models.TextField(help_text='PayMongo secret API key (sk_live_… / sk_test_…).')),
                ('secret', models.TextField(blank=True, default='', help_text='PayMongo webhook signing secret.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('account', models.ForeignKey(db_column='account_id', on_delete=django.db.models.deletion.CASCADE, related_name='payment_integrations', to='users.account')),
                ('company', models.ForeignKey(db_column='company_id', on_delete=django.db.models.deletion.CASCADE, related_name='payment_integrations', to='companies.company')),
                ('created_by', models.ForeignKey(blank=True, db_column='created_by', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_integrations_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'payment_integrations',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='paymentintegration',
            constraint=models.UniqueConstraint(condition=models.Q(('deleted_at__isnull', True)), fields=('company', 'payment_gateway'), name='payment_integrations_one_gateway_per_company'),
        ),
    ]
