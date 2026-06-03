from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0022_emailtemplate_cc_bcc'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emaillog',
            name='created_at',
            field=models.DateTimeField(),
        ),
    ]
