from decimal import Decimal

from django.db import migrations

PRO_BASE_PRICE_KEY = 'subscription_pro_base_price'
PRO_PRICE_PER_USER_KEY = 'subscription_pro_price_per_user'
AI_BASE_PRICE_KEY = 'subscription_ai_base_price'
AI_PRICE_PER_USER_KEY = 'subscription_ai_price_per_user'

DEFAULTS = {
    PRO_BASE_PRICE_KEY: '995.00',
    PRO_PRICE_PER_USER_KEY: '100.00',
    AI_BASE_PRICE_KEY: '1495.00',
    AI_PRICE_PER_USER_KEY: '150.00',
}


def seed_subscription_plan_pricing(apps, schema_editor):
    SystemSetting = apps.get_model('system_settings', 'SystemSetting')
    for key, default in DEFAULTS.items():
        SystemSetting.objects.get_or_create(
            name=key,
            defaults={'value': default},
        )

    Subscription = apps.get_model('subscriptions', 'Subscription')
    pro_base = Decimal(DEFAULTS[PRO_BASE_PRICE_KEY])
    pro_per_user = Decimal(DEFAULTS[PRO_PRICE_PER_USER_KEY])
    ai_base = Decimal(DEFAULTS[AI_BASE_PRICE_KEY])
    ai_per_user = Decimal(DEFAULTS[AI_PRICE_PER_USER_KEY])

    Subscription.objects.filter(plan='pro').update(
        base_price=pro_base,
        price_per_user=pro_per_user,
    )
    Subscription.objects.filter(plan='ai').update(
        base_price=ai_base,
        price_per_user=ai_per_user,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('system_settings', '0003_seed_subscription_payment_provider'),
        ('subscriptions', '0008_subscriptionfailedpaymentnotice'),
    ]

    operations = [
        migrations.RunPython(
            seed_subscription_plan_pricing,
            migrations.RunPython.noop,
        ),
    ]
