from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0035_ai_assistant_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='account_restricted',
            field=models.BooleanField(
                default=False,
                help_text='When true, the user is read-only in the Users list (no edit/delete).',
            ),
        ),
    ]
