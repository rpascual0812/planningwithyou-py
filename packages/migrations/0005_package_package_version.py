from django.db import migrations, models
import django.db.models.deletion


def backfill_package_versions(apps, schema_editor):
    Package = apps.get_model('packages', 'Package')
    PackageVersion = apps.get_model('packages', 'PackageVersion')

    for pkg in Package.objects.filter(package_version_id__isnull=True).iterator():
        version = (
            PackageVersion.objects.filter(
                account_id=pkg.account_id,
                company_id=pkg.company_id,
                title='Default',
                deleted_at__isnull=True,
            )
            .order_by('id')
            .first()
        )
        if version is None:
            version = PackageVersion.objects.create(
                title='Default',
                description='',
                is_active=True,
                account_id=pkg.account_id,
                company_id=pkg.company_id,
                created_by_id=pkg.created_by_id,
            )
        pkg.package_version_id = version.id
        pkg.save(update_fields=['package_version_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('packages', '0004_packageversion'),
    ]

    operations = [
        migrations.AddField(
            model_name='package',
            name='package_version',
            field=models.ForeignKey(
                blank=True,
                db_column='package_version_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='packages',
                to='packages.packageversion',
            ),
        ),
        migrations.RunPython(backfill_package_versions, noop),
        migrations.AlterField(
            model_name='package',
            name='package_version',
            field=models.ForeignKey(
                db_column='package_version_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='packages',
                to='packages.packageversion',
            ),
        ),
    ]
