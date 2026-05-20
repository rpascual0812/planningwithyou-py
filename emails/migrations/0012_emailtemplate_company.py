import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_company_supplier_type'),
        ('emails', '0011_alter_emailtemplate_template_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailtemplate',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='email_templates',
                to='companies.company',
            ),
        ),
    ]
