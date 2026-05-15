from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_account_supplier_type_remove_is_supplier'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='discount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='account',
            name='price_adjustment',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
