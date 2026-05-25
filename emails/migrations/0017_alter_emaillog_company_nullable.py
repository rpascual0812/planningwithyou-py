import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_company_supplier_type'),
        ('emails', '0016_payment_link_template_per_company'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emaillog',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='email_logs',
                to='companies.company',
            ),
        ),
    ]
