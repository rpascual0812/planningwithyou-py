from django.db import migrations, models


def disable_ai_plus(apps, schema_editor):
    Subscription = apps.get_model('subscriptions', 'Subscription')
    Subscription.objects.filter(plan='ai').update(is_selectable=False)


def enable_ai_plus(apps, schema_editor):
    Subscription = apps.get_model('subscriptions', 'Subscription')
    Subscription.objects.filter(plan='ai').update(is_selectable=True)


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0002_seed_subscriptions'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='is_selectable',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(disable_ai_plus, enable_ai_plus),
    ]
