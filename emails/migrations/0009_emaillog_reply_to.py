from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0008_remove_emaillog_body_text_rename_body_html_body'),
    ]

    operations = [
        migrations.AddField(
            model_name='emaillog',
            name='reply_to',
            field=models.EmailField(
                blank=True,
                default='',
                help_text='Optional reply-to address (single recipient).',
                max_length=254,
            ),
        ),
    ]
