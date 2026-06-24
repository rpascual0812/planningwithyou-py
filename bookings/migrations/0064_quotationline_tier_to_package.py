import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0063_quotation_pricing_adjustments'),
        ('suppliers', '0011_rename_tier_to_package'),
    ]

    operations = [
        migrations.RenameField(
            model_name='quotationline',
            old_name='tier',
            new_name='package',
        ),
        migrations.AlterField(
            model_name='quotationline',
            name='package',
            field=models.ForeignKey(
                blank=True,
                db_column='package_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='quotation_lines',
                to='suppliers.package',
            ),
        ),
    ]
