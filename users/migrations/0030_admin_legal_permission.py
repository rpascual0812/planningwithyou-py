from django.db import migrations

ADMIN_LEGAL = 'admin_legal'


def grant_admin_legal_from_platform_admin(apps, schema_editor):
    Role = apps.get_model('users', 'Role')
    RolePermission = apps.get_model('users', 'RolePermission')

    for role in Role.objects.all().iterator():
        source = RolePermission.objects.filter(
            role_id=role.id,
            feature_key='platform_admin',
        ).first()
        access = source.access if source is not None else 'none'
        if access == 'none':
            continue
        RolePermission.objects.get_or_create(
            role_id=role.id,
            feature_key=ADMIN_LEGAL,
            defaults={'access': access},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0029_change_company_permission'),
        ('system_settings', '0002_seed_legal_documents'),
    ]

    operations = [
        migrations.RunPython(
            grant_admin_legal_from_platform_admin,
            migrations.RunPython.noop,
        ),
    ]
