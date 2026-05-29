from django.db import migrations

NEW_FEATURE = 'template_studio'
COPY_FROM = 'file_manager'


def add_template_studio_permission(apps, schema_editor):
    Role = apps.get_model('users', 'Role')
    RolePermission = apps.get_model('users', 'RolePermission')

    for role in Role.objects.all().iterator():
        if RolePermission.objects.filter(
            role_id=role.id,
            feature_key=NEW_FEATURE,
        ).exists():
            continue
        source = RolePermission.objects.filter(
            role_id=role.id,
            feature_key=COPY_FROM,
        ).first()
        access = source.access if source is not None else 'none'
        if role.name == 'Owner' and access == 'none':
            access = 'write'
        RolePermission.objects.create(
            role_id=role.id,
            feature_key=NEW_FEATURE,
            access=access,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0030_admin_legal_permission'),
    ]

    operations = [
        migrations.RunPython(add_template_studio_permission, migrations.RunPython.noop),
    ]
