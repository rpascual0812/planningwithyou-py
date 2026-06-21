from django.db import migrations

SUBSCRIPTION_PAYMENT_PROVIDER_KEY = 'subscription_payment_provider'
DEFAULT_PROVIDER = 'paymongo'


def seed_subscription_payment_provider(apps, schema_editor):
    SystemSetting = apps.get_model('system_settings', 'SystemSetting')
    SystemSetting.objects.get_or_create(
        name=SUBSCRIPTION_PAYMENT_PROVIDER_KEY,
        defaults={'value': DEFAULT_PROVIDER},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('system_settings', '0002_seed_legal_documents'),
    ]

    operations = [
        migrations.RunPython(
            seed_subscription_payment_provider,
            migrations.RunPython.noop,
        ),
    ]
