from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_paymongo_platform_child_account'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebhookLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'source',
                    models.CharField(
                        help_text='Webhook origin (e.g. paymongo).',
                        max_length=127,
                    ),
                ),
                (
                    'payload',
                    models.JSONField(help_text='Full webhook request body as received.'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'webhook_logs',
                'ordering': ['-created_at'],
            },
        ),
    ]
