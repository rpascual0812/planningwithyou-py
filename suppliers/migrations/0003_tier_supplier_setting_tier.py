import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('suppliers', '0002_supplier_setting'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        db_column='created_by_id',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='tiers_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'tiers',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='SupplierSettingTier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('discount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                (
                    'discount_type',
                    models.CharField(
                        choices=[('percent', 'Percent'), ('fixed', 'Fixed amount')],
                        default='percent',
                        max_length=20,
                    ),
                ),
                ('price_adjustment', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                (
                    'price_adjustment_type',
                    models.CharField(
                        choices=[('percent', 'Percent'), ('fixed', 'Fixed amount')],
                        default='percent',
                        max_length=20,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'supplier_setting',
                    models.ForeignKey(
                        db_column='supplier_setting_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='tiers',
                        to='suppliers.suppliersetting',
                    ),
                ),
                (
                    'tier',
                    models.ForeignKey(
                        db_column='tier_id',
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='supplier_setting_tiers',
                        to='suppliers.tier',
                    ),
                ),
            ],
            options={
                'db_table': 'supplier_setting_tiers',
                'ordering': ['tier__name', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='suppliersettingtier',
            constraint=models.UniqueConstraint(
                fields=('supplier_setting', 'tier'),
                name='supplier_setting_tiers_setting_tier_uniq',
            ),
        ),
    ]
