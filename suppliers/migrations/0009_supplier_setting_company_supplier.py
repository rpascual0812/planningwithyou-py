from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0008_clear_supplier_settings_for_company_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='suppliersetting',
            name='supplier',
            field=models.ForeignKey(
                db_column='supplier_id',
                on_delete=models.deletion.CASCADE,
                related_name='supplier_settings_as_supplier',
                to='companies.company',
            ),
        ),
    ]
