from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0006_restore_active_tiers'),
    ]

    operations = [
        migrations.RenameField(
            model_name='suppliersettingtier',
            old_name='price_adjustment',
            new_name='mark_up',
        ),
        migrations.RenameField(
            model_name='suppliersettingtier',
            old_name='price_adjustment_type',
            new_name='mark_up_type',
        ),
        migrations.AddField(
            model_name='suppliersettingtier',
            name='price_override',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
            ),
        ),
        migrations.AddField(
            model_name='suppliersettingtier',
            name='tax',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
            ),
        ),
    ]
