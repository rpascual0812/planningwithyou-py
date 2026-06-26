import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('companies', '0001_initial'),
        ('users', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('general', 'General'), ('google_calendar', 'Google Calendar'), ('gmail', 'Gmail')], db_index=True, default='general', max_length=32)),
                ('severity', models.CharField(choices=[('info', 'Info'), ('warning', 'Warning'), ('error', 'Error')], default='error', max_length=16)),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('action_url', models.CharField(blank=True, default='', max_length=512)),
                ('dedupe_key', models.CharField(blank=True, db_index=True, default='', max_length=255)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(db_column='account_id', on_delete=django.db.models.deletion.CASCADE, related_name='user_notifications', to='users.account')),
                ('company', models.ForeignKey(blank=True, db_column='company_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_notifications', to='companies.company')),
                ('user', models.ForeignKey(db_column='user_id', on_delete=django.db.models.deletion.CASCADE, related_name='user_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_notifications',
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['user', 'deleted_at', 'read_at', '-created_at'], name='user_notif_user_read_idx')],
            },
        ),
    ]
