from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_webhooklog'),
    ]

    operations = [
        migrations.AddField(
            model_name='webhooklog',
            name='processed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When business logic finished processing this payload.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='webhooklog',
            name='handled',
            field=models.BooleanField(
                blank=True,
                help_text='Whether any handler applied this webhook to app state.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='webhooklog',
            name='error_message',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Validation or processing error, if any.',
            ),
        ),
    ]
