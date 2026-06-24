from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0001_supplier_type'),
        ('bookings', '0064_quotationline_tier_to_package'),
    ]

    operations = [
        migrations.AddField(
            model_name='formtemplatefield',
            name='supplier_type',
            field=models.ForeignKey(
                blank=True,
                db_column='supplier_type_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='suppliers.suppliertype',
            ),
        ),
    ]
