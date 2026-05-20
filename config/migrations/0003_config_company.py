import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_company_supplier_type'),
        ('config', '0002_config_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='config',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='configs',
                to='companies.company',
            ),
        ),
    ]
