import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_account_discount_price_adjustment'),
        ('suppliers', '0001_supplier_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupplierSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'account',
                    models.ForeignKey(
                        db_column='account_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='supplier_settings_as_account',
                        to='users.account',
                    ),
                ),
                (
                    'supplier',
                    models.ForeignKey(
                        db_column='supplier_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='supplier_settings_as_supplier',
                        to='users.account',
                    ),
                ),
            ],
            options={
                'db_table': 'supplier_settings',
                'ordering': ['-updated_at', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='suppliersetting',
            constraint=models.UniqueConstraint(
                fields=('supplier', 'account'),
                name='supplier_settings_supplier_account_uniq',
            ),
        ),
    ]
