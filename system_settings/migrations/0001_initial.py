from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SystemSetting',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.TextField(unique=True)),
                ('value', models.TextField(blank=True, default='')),
            ],
            options={
                'db_table': 'system',
                'ordering': ['name'],
            },
        ),
    ]
