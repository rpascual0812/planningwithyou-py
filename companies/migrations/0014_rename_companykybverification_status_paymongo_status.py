from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0013_companykybverification_xendit'),
    ]

    operations = [
        migrations.RenameField(
            model_name='companykybverification',
            old_name='status',
            new_name='paymongo_status',
        ),
    ]
