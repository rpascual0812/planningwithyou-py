from django.db import migrations

ADMIN_ERROR_LOGS = 'admin_error_logs'


def grant_admin_error_logs_from_platform_admin(apps, schema_editor):
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
            feature_key=ADMIN_ERROR_LOGS,
            defaults={'access': access},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0033_admin_accounts_permission'),
    ]

    operations = [
        migrations.RunPython(
            grant_admin_error_logs_from_platform_admin,
            migrations.RunPython.noop,
        ),
    ]
