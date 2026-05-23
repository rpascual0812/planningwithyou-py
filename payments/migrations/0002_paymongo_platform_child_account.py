from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_payment_integration'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentintegration',
            name='paymongo_account_id',
            field=models.CharField(
                blank=True,
                default='',
                help_text='PayMongo linked child account id (org_…).',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='paymentintegration',
            name='activation_status',
            field=models.CharField(
                blank=True,
                default='not_started',
                help_text='PayMongo child account activation_status.',
                max_length=63,
            ),
        ),
        migrations.AddField(
            model_name='paymentintegration',
            name='identity_verification_status',
            field=models.CharField(
                blank=True,
                default='',
                help_text='PayMongo identity_verification_status for the representative.',
                max_length=63,
            ),
        ),
        migrations.AddField(
            model_name='paymentintegration',
            name='identity_verification_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Hosted URL for the representative to complete PayMongo KYC.',
                max_length=2048,
            ),
        ),
        migrations.AddField(
            model_name='paymentintegration',
            name='api_response',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name='paymentintegration',
            name='key',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Deprecated: use PayMongo Platforms child account instead.',
            ),
        ),
        migrations.AlterField(
            model_name='paymentintegration',
            name='secret',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Deprecated: platform webhook secret is used.',
            ),
        ),
    ]
