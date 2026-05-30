from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0031_template_studio_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='tour_completed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the user finished or skipped the in-app product tour.',
                null=True,
            ),
        ),
    ]
