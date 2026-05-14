# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0003_emailtemplate_body_type_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailtemplate',
            name='subject',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
