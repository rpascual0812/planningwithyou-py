from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0020_user_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='token_version',
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    'Incremented on each login to invalidate JWTs from previous sessions.'
                ),
            ),
        ),
    ]
