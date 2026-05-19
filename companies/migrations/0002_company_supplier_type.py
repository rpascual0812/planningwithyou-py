from django.db import migrations, models


def backfill_company_supplier_type(apps, schema_editor):
    Account = apps.get_model('users', 'Account')
    Company = apps.get_model('companies', 'Company')

    for account in Account.objects.exclude(supplier_type_id__isnull=True).iterator():
        Company.objects.filter(account_id=account.id).update(
            supplier_type_id=account.supplier_type_id,
        )

    Company.objects.filter(supplier_type_id__isnull=True).update(supplier_type_id=1)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        ('users', '0015_user_company'),
        ('suppliers', '0001_supplier_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='supplier_type',
            field=models.ForeignKey(
                blank=True,
                db_column='supplier_type_id',
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name='companies',
                to='suppliers.suppliertype',
            ),
        ),
        migrations.RunPython(backfill_company_supplier_type, noop),
        migrations.AlterField(
            model_name='company',
            name='supplier_type',
            field=models.ForeignKey(
                db_column='supplier_type_id',
                on_delete=models.deletion.PROTECT,
                related_name='companies',
                to='suppliers.suppliertype',
            ),
        ),
    ]
