from django.db import migrations

ADMIN_SUBSCRIPTIONS = 'admin_subscriptions'


def grant_admin_subscriptions_from_platform_admin(apps, schema_editor):
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
            feature_key=ADMIN_SUBSCRIPTIONS,
            defaults={'access': access},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0036_user_account_restricted'),
    ]

    operations = [
        migrations.RunPython(
            grant_admin_subscriptions_from_platform_admin,
            migrations.RunPython.noop,
        ),
    ]
