from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('packages', '0011_alter_package_ordering'),
    ]

    operations = [
        migrations.AddField(
            model_name='package',
            name='required_downpayment_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
