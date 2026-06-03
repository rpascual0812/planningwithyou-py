from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0021_seed_kyb_verified_email_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailtemplate',
            name='bcc',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Default BCC email addresses for messages using this template.',
            ),
        ),
        migrations.AddField(
            model_name='emailtemplate',
            name='cc',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Default CC email addresses for messages using this template.',
            ),
        ),
    ]
