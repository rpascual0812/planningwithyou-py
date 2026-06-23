from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('template_studio', '0006_invitation_template_unique_title_slug'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitationtemplate',
            name='view_count',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
