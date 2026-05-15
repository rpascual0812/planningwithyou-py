from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_account_price'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='price',
        ),
    ]
