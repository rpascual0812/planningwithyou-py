import django.db.models.deletion
from django.db import migrations, models


def assign_package_tiers(apps, schema_editor):
    Package = apps.get_model('packages', 'Package')
    Tier = apps.get_model('suppliers', 'Tier')
    for package in Package.objects.iterator():
        tier = (
            Tier.objects.filter(
                company_id=package.company_id,
                account_id=package.account_id,
                deleted_at__isnull=True,
            )
            .order_by('name', 'id')
            .first()
        )
        if tier is None:
            tier = Tier.objects.create(
                account_id=package.account_id,
                company_id=package.company_id,
                name='Default',
                is_active=True,
            )
        package.tier_id = tier.id
        package.save(update_fields=['tier_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('packages', '0008_packageitem_parent_sort_order'),
        ('suppliers', '0010_tier_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='package',
            name='tier',
            field=models.ForeignKey(
                db_column='tier_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='packages',
                to='suppliers.tier',
            ),
        ),
        migrations.RunPython(assign_package_tiers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='package',
            name='tier',
            field=models.ForeignKey(
                db_column='tier_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='packages',
                to='suppliers.tier',
            ),
        ),
        migrations.RemoveField(
            model_name='package',
            name='title',
        ),
        migrations.AlterModelOptions(
            name='package',
            options={'ordering': ['tier_id', 'id']},
        ),
    ]
