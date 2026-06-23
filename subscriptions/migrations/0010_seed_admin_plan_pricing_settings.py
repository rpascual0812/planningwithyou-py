from decimal import Decimal

from django.db import migrations

ADMIN_BASE_PRICE_KEY = 'subscription_admin_base_price'
ADMIN_PRICE_PER_USER_KEY = 'subscription_admin_price_per_user'

DEFAULTS = {
    ADMIN_BASE_PRICE_KEY: '0.00',
    ADMIN_PRICE_PER_USER_KEY: '0.00',
}


def seed_admin_plan_pricing(apps, schema_editor):
    SystemSetting = apps.get_model('system_settings', 'SystemSetting')
    for key, default in DEFAULTS.items():
        SystemSetting.objects.get_or_create(
            name=key,
            defaults={'value': default},
        )

    Subscription = apps.get_model('subscriptions', 'Subscription')
    admin_base = Decimal(DEFAULTS[ADMIN_BASE_PRICE_KEY])
    admin_per_user = Decimal(DEFAULTS[ADMIN_PRICE_PER_USER_KEY])
    Subscription.objects.filter(plan='admin').update(
        base_price=admin_base,
        price_per_user=admin_per_user,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('system_settings', '0004_seed_subscription_plan_pricing'),
        ('subscriptions', '0009_seed_admin_plan'),
    ]

    operations = [
        migrations.RunPython(seed_admin_plan_pricing, migrations.RunPython.noop),
    ]
