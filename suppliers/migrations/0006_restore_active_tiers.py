from django.db import migrations


def restore_soft_deleted_active_tiers(apps, schema_editor):
    Tier = apps.get_model('suppliers', 'Tier')
    Tier.objects.filter(is_active=True).exclude(deleted_at=None).update(
        deleted_at=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0005_supplier_setting_tier_price'),
    ]

    operations = [
        migrations.RunPython(
            restore_soft_deleted_active_tiers,
            migrations.RunPython.noop,
        ),
    ]
