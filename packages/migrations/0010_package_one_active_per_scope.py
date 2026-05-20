from django.db import migrations, models
from django.db.models import Count


def dedupe_active_packages(apps, schema_editor):
    Package = apps.get_model('packages', 'Package')
    duplicate_groups = (
        Package.objects.filter(deleted_at__isnull=True, is_active=True)
        .order_by()
        .values('company_id', 'tier_id', 'package_version_id')
        .annotate(active_count=Count('id'))
        .filter(active_count__gt=1)
    )
    for group in duplicate_groups:
        packages = Package.objects.filter(
            company_id=group['company_id'],
            tier_id=group['tier_id'],
            package_version_id=group['package_version_id'],
            deleted_at__isnull=True,
            is_active=True,
        ).order_by('id')
        keeper = packages.first()
        if keeper is not None:
            packages.exclude(pk=keeper.pk).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('packages', '0009_package_tier_remove_title'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='package',
            options={'ordering': ['tier_id', 'id']},
        ),
        migrations.RunPython(dedupe_active_packages, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='package',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                fields=('company', 'tier', 'package_version'),
                name='packages_one_active_per_company_tier_version',
            ),
        ),
    ]
