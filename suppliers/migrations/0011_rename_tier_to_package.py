import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_company_supplier_type'),
        ('suppliers', '0010_tier_company'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Tier',
            new_name='Package',
        ),
        migrations.AlterModelTable(
            name='package',
            table='packages',
        ),
        migrations.AlterField(
            model_name='package',
            name='account',
            field=models.ForeignKey(
                db_column='account_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='packages',
                to='users.account',
            ),
        ),
        migrations.AlterField(
            model_name='package',
            name='company',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='packages',
                to='companies.company',
            ),
        ),
        migrations.AlterField(
            model_name='package',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                db_column='created_by_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='packages_created',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RenameModel(
            old_name='SupplierSettingTier',
            new_name='SupplierSettingPackage',
        ),
        migrations.AlterModelTable(
            name='suppliersettingpackage',
            table='supplier_setting_packages',
        ),
        migrations.RenameField(
            model_name='suppliersettingpackage',
            old_name='tier',
            new_name='package',
        ),
        migrations.AlterField(
            model_name='suppliersettingpackage',
            name='package',
            field=models.ForeignKey(
                db_column='package_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='supplier_setting_packages',
                to='suppliers.package',
            ),
        ),
        migrations.RemoveConstraint(
            model_name='suppliersettingpackage',
            name='supplier_setting_tiers_setting_tier_uniq',
        ),
        migrations.AddConstraint(
            model_name='suppliersettingpackage',
            constraint=models.UniqueConstraint(
                fields=('supplier_setting', 'package'),
                name='supplier_setting_packages_setting_package_uniq',
            ),
        ),
        migrations.AlterModelOptions(
            name='suppliersettingpackage',
            options={'ordering': ['package__name', 'id']},
        ),
    ]
