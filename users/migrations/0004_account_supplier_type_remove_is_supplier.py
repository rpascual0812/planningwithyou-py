import django.db.models.deletion
from django.db import migrations, models


def ensure_supplier_type_1(apps, schema_editor):
    SupplierType = apps.get_model('suppliers', 'SupplierType')
    if not SupplierType.objects.filter(pk=1).exists():
        SupplierType.objects.create(pk=1, name='Ceremony venue', is_active=True)


def backfill_account_supplier_type(apps, schema_editor):
    Account = apps.get_model('users', 'Account')
    Account.objects.filter(supplier_type_id__isnull=True).update(supplier_type_id=1)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0001_supplier_type'),
        ('users', '0003_account_is_supplier'),
    ]

    operations = [
        migrations.RunPython(ensure_supplier_type_1, noop),
        migrations.AddField(
            model_name='account',
            name='supplier_type',
            field=models.ForeignKey(
                db_column='supplier_type_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='accounts',
                to='suppliers.suppliertype',
            ),
        ),
        migrations.RunPython(backfill_account_supplier_type, noop),
        migrations.AlterField(
            model_name='account',
            name='supplier_type',
            field=models.ForeignKey(
                db_column='supplier_type_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='accounts',
                to='suppliers.suppliertype',
            ),
        ),
        migrations.RemoveField(
            model_name='account',
            name='is_supplier',
        ),
    ]
