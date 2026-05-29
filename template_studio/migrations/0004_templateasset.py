import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import template_studio.models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0004_company_kyb_verification'),
        ('users', '0013_migrate_account_logos_to_companies'),
        ('template_studio', '0003_seed_canva_modern_elegance'),
    ]

    operations = [
        migrations.CreateModel(
            name='TemplateAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('file', models.FileField(upload_to=template_studio.models.template_asset_upload_path)),
                ('original_name', models.CharField(max_length=255)),
                ('mime_type', models.CharField(blank=True, default='', max_length=100)),
                ('size', models.PositiveBigIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'account',
                    models.ForeignKey(
                        db_column='account_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='template_assets',
                        to='users.account',
                    ),
                ),
                (
                    'company',
                    models.ForeignKey(
                        db_column='company_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='template_assets',
                        to='companies.company',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        db_column='created_by_id',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='template_assets',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'template_studio_assets',
                'ordering': ['-created_at'],
            },
        ),
    ]
