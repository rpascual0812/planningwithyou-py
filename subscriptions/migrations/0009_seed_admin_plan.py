from decimal import Decimal

from django.db import migrations


def seed_admin_plan(apps, schema_editor):
    Subscription = apps.get_model('subscriptions', 'Subscription')
    row = {
        'plan': 'admin',
        'name': 'Admin',
        'subtitle': 'Internal platform staff plan',
        'features': [
            'Everything in AI Plus',
            'Multiple companies and users',
            'No charge',
        ],
        'base_price': Decimal('0'),
        'price_per_user': Decimal('0'),
        'default_users': 1,
        'has_team_stepper': True,
        'is_active': True,
        'is_selectable': True,
        'sort_order': 3,
    }
    for cycle in ('monthly', 'yearly'):
        Subscription.objects.update_or_create(
            plan='admin',
            billing_cycle=cycle,
            defaults=row,
        )


def unseed_admin_plan(apps, schema_editor):
    Subscription = apps.get_model('subscriptions', 'Subscription')
    Subscription.objects.filter(plan='admin').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0008_subscriptionfailedpaymentnotice'),
    ]

    operations = [
        migrations.RunPython(seed_admin_plan, unseed_admin_plan),
    ]
