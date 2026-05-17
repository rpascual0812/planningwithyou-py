from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('countries', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='country',
            old_name='iso_code',
            new_name='iso2_code',
        ),
    ]
