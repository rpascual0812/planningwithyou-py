from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_account_country'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='country',
        ),
    ]
