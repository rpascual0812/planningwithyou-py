from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_account_discount_price_adjustment'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='price',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
            ),
        ),
    ]
