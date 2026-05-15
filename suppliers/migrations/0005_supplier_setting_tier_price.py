from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0004_tier_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='suppliersettingtier',
            name='price',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
            ),
        ),
    ]
