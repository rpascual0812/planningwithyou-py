"""Grant ai_assistant permission to existing roles (copy from quotations)."""

from django.db import migrations

FEATURE_KEY = 'ai_assistant'
COPY_FROM = 'quotations'


def grant_ai_assistant_permission(apps, schema_editor):
    Role = apps.get_model('users', 'Role')
    RolePermission = apps.get_model('users', 'RolePermission')

    for role in Role.objects.all().iterator():
        if RolePermission.objects.filter(
            role_id=role.id,
            feature_key=FEATURE_KEY,
        ).exists():
            continue
        source = RolePermission.objects.filter(
            role_id=role.id,
            feature_key=COPY_FROM,
        ).first()
        access = source.access if source is not None else 'write'
        RolePermission.objects.create(
            role_id=role.id,
            feature_key=FEATURE_KEY,
            access=access,
        )


def revoke_ai_assistant_permission(apps, schema_editor):
    RolePermission = apps.get_model('users', 'RolePermission')
    RolePermission.objects.filter(feature_key=FEATURE_KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0034_admin_error_logs_permission'),
    ]

    operations = [
        migrations.RunPython(
            grant_ai_assistant_permission,
            revoke_ai_assistant_permission,
        ),
    ]
