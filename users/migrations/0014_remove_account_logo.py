from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0013_migrate_account_logos_to_companies'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='logo',
        ),
    ]
