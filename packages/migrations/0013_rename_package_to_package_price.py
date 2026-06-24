import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('packages', '0012_package_required_downpayment_amount'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Package',
            new_name='PackagePrice',
        ),
        migrations.AlterModelTable(
            name='packageprice',
            table='package_prices',
        ),
        migrations.RemoveConstraint(
            model_name='packageprice',
            name='packages_one_active_per_company_tier_version',
        ),
        migrations.AddConstraint(
            model_name='packageprice',
            constraint=models.UniqueConstraint(
                fields=('company', 'tier', 'package_version'),
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name='package_prices_one_active_per_company_tier_version',
            ),
        ),
        migrations.AlterField(
            model_name='packageprice',
            name='account',
            field=models.ForeignKey(
                db_column='account_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='package_prices',
                to='users.account',
            ),
        ),
        migrations.AlterField(
            model_name='packageprice',
            name='company',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='package_prices',
                to='companies.company',
            ),
        ),
        migrations.AlterField(
            model_name='packageprice',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                db_column='created_by',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='package_prices_created',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='packageprice',
            name='package_version',
            field=models.ForeignKey(
                db_column='package_version_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='package_prices',
                to='packages.packageversion',
            ),
        ),
        migrations.AlterField(
            model_name='packageprice',
            name='tier',
            field=models.ForeignKey(
                db_column='tier_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='package_prices',
                to='suppliers.tier',
            ),
        ),
        migrations.RenameField(
            model_name='packageitem',
            old_name='package',
            new_name='package_price',
        ),
        migrations.AlterField(
            model_name='packageitem',
            name='package_price',
            field=models.ForeignKey(
                db_column='package_price_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='items',
                to='packages.packageprice',
            ),
        ),
    ]
