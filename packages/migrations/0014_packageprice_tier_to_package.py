import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('packages', '0013_rename_package_to_package_price'),
        ('suppliers', '0011_rename_tier_to_package'),
    ]

    operations = [
        migrations.RenameField(
            model_name='packageprice',
            old_name='tier',
            new_name='package',
        ),
        migrations.RemoveConstraint(
            model_name='packageprice',
            name='package_prices_one_active_per_company_tier_version',
        ),
        migrations.AddConstraint(
            model_name='packageprice',
            constraint=models.UniqueConstraint(
                fields=('company', 'package', 'package_version'),
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name='package_prices_one_active_per_company_package_version',
            ),
        ),
        migrations.AlterField(
            model_name='packageprice',
            name='package',
            field=models.ForeignKey(
                db_column='package_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='package_prices',
                to='suppliers.package',
            ),
        ),
    ]
