import django.db.models.deletion
from django.db import migrations, models


def set_tier_account_id(apps, schema_editor):
    Tier = apps.get_model('suppliers', 'Tier')
    Tier.objects.filter(account_id__isnull=True).update(account_id=1)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_account_discount_price_adjustment'),
        ('suppliers', '0003_tier_supplier_setting_tier'),
    ]

    operations = [
        migrations.AddField(
            model_name='tier',
            name='account',
            field=models.ForeignKey(
                db_column='account_id',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tiers',
                to='users.account',
            ),
        ),
        migrations.RunPython(set_tier_account_id, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='tier',
            name='account',
            field=models.ForeignKey(
                db_column='account_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tiers',
                to='users.account',
            ),
        ),
    ]
