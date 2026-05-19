from django.db import migrations


def clear_supplier_settings(apps, schema_editor):
    """Existing rows reference account suppliers; reset before FK targets companies."""
    SupplierSettingTier = apps.get_model('suppliers', 'SupplierSettingTier')
    SupplierSetting = apps.get_model('suppliers', 'SupplierSetting')
    SupplierSettingTier.objects.all().delete()
    SupplierSetting.objects.all().delete()


class Migration(migrations.Migration):
    # Commit deletes before 0009 alters the FK (avoids PostgreSQL pending-trigger error).
    atomic = False

    dependencies = [
        ('suppliers', '0007_rename_markup_add_override_tax'),
        ('companies', '0002_company_supplier_type'),
    ]

    operations = [
        migrations.RunPython(clear_supplier_settings, migrations.RunPython.noop),
    ]
