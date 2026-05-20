import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0032_bookingline_company_tier_package_version'),
        ('companies', '0002_company_supplier_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='formtemplate',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='form_templates',
                to='companies.company',
            ),
        ),
    ]
