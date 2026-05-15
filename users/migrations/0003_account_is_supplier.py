from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_alter_user_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='is_supplier',
            field=models.BooleanField(default=False),
        ),
    ]
