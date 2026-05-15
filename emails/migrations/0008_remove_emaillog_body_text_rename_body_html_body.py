from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0007_alter_emaillog_account_alter_emailtemplate_account'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='emaillog',
            name='body_text',
        ),
        migrations.RenameField(
            model_name='emaillog',
            old_name='body_html',
            new_name='body',
        ),
    ]
