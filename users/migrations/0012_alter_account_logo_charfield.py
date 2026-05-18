from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0011_account_logo_contact_timezone_remove_discount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='account',
            name='logo',
            field=models.CharField(
                blank=True,
                default='',
                help_text='S3/local storage object key for the account logo (e.g. account_logos/…).',
                max_length=512,
            ),
        ),
    ]
