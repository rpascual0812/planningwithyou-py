import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('config', '0003_config_company'),
    ]

    operations = [
        migrations.CreateModel(
            name='ErrorLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method', models.CharField(max_length=16)),
                ('path', models.TextField()),
                ('query_string', models.TextField(blank=True, default='')),
                ('status_code', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('exception_type', models.CharField(blank=True, default='', max_length=255)),
                ('exception_message', models.TextField(blank=True, default='')),
                ('traceback', models.TextField(blank=True, default='')),
                ('request_body', models.TextField(blank=True, default='')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(
                    blank=True,
                    db_column='account_id',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='error_logs',
                    to='users.account',
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    db_column='user_id',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='error_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'error_logs',
                'ordering': ['-created_at'],
            },
        ),
    ]
