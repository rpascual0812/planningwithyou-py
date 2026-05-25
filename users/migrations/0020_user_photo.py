from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0019_user_is_verified_email_verification_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='photo',
            field=models.CharField(blank=True, default='', max_length=512),
        ),
    ]
