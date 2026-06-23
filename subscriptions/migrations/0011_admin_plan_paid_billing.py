from decimal import Decimal

from django.db import migrations

ADMIN_BASE_PRICE_KEY = 'subscription_admin_base_price'
ADMIN_PRICE_PER_USER_KEY = 'subscription_admin_price_per_user'

DEFAULTS = {
    ADMIN_BASE_PRICE_KEY: '995.00',
    ADMIN_PRICE_PER_USER_KEY: '100.00',
}


def set_admin_plan_paid_defaults(apps, schema_editor):
    SystemSetting = apps.get_model('system_settings', 'SystemSetting')
    for key, default in DEFAULTS.items():
        SystemSetting.objects.update_or_create(
            name=key,
            defaults={'value': default},
        )

    Subscription = apps.get_model('subscriptions', 'Subscription')
    admin_base = Decimal(DEFAULTS[ADMIN_BASE_PRICE_KEY])
    admin_per_user = Decimal(DEFAULTS[ADMIN_PRICE_PER_USER_KEY])
    Subscription.objects.filter(plan='admin').update(
        base_price=admin_base,
        price_per_user=admin_per_user,
        subtitle='Internal platform staff plan (live billing)',
        features=[
            'Everything in AI Plus',
            'Multiple companies and users',
            'Recurring subscription billing for testing',
        ],
    )


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0010_seed_admin_plan_pricing_settings'),
    ]

    operations = [
        migrations.RunPython(set_admin_plan_paid_defaults, migrations.RunPython.noop),
    ]
