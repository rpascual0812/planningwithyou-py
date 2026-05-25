import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def verify_existing_users(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.filter(is_verified=False).update(is_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0018_remove_account_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(verify_existing_users, migrations.RunPython.noop),
        migrations.CreateModel(
            name='EmailVerificationToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('used', models.BooleanField(default=False)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='email_verification_tokens',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'email_verification_tokens',
                'ordering': ['-created_at'],
            },
        ),
    ]
