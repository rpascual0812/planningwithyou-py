from decimal import Decimal

from django.db import migrations


def seed_subscriptions(apps, schema_editor):
    Subscription = apps.get_model('subscriptions', 'Subscription')
    rows = [
        {
            'plan': 'free',
            'name': 'Free',
            'subtitle': 'Advanced features are limited',
            'features': [],
            'base_price': Decimal('0'),
            'price_per_user': Decimal('0'),
            'default_users': 1,
            'has_team_stepper': False,
            'sort_order': 0,
        },
        {
            'plan': 'pro',
            'name': 'Pro',
            'subtitle': 'All features are available',
            'features': [
                'Access to Email and Calendar Integrations',
                'Access to Supplier Selection',
                'Allow Multiple Companies',
                'Allow Multiple Users',
            ],
            'base_price': Decimal('995.00'),
            'price_per_user': Decimal('100.00'),
            'default_users': 1,
            'has_team_stepper': True,
            'sort_order': 1,
        },
        {
            'plan': 'ai',
            'name': 'AI Plus',
            'subtitle': 'For teams that need AI features',
            'features': [
                'Everything Pro.',
                'AI Automation',
            ],
            'base_price': Decimal('1495.00'),
            'price_per_user': Decimal('150.00'),
            'default_users': 1,
            'has_team_stepper': True,
            'sort_order': 2,
        },
    ]
    for row in rows:
        for cycle in ('monthly', 'yearly'):
            Subscription.objects.create(
                billing_cycle=cycle,
                is_active=True,
                **row,
            )


def unseed_subscriptions(apps, schema_editor):
    Subscription = apps.get_model('subscriptions', 'Subscription')
    Subscription.objects.filter(
        plan__in=['free', 'pro', 'ai'],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0001_subscription'),
    ]

    operations = [
        migrations.RunPython(seed_subscriptions, unseed_subscriptions),
    ]
