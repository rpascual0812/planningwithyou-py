from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0001_initial'),
        ('calendars', '0006_calendar_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendar',
            name='google_event_id',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Google Calendar event id when synced.',
                max_length=255,
            ),
        ),
        migrations.CreateModel(
            name='GoogleCalendarIntegration',
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
                ('google_email', models.EmailField(blank=True, default='', max_length=255)),
                (
                    'google_calendar_id',
                    models.CharField(
                        blank=True,
                        default='primary',
                        help_text='Google calendar id (usually primary).',
                        max_length=255,
                    ),
                ),
                ('access_token_encrypted', models.TextField(blank=True, default='')),
                ('refresh_token_encrypted', models.TextField(blank=True, default='')),
                ('token_expiry', models.DateTimeField(blank=True, null=True)),
                (
                    'sync_mode',
                    models.CharField(
                        choices=[
                            ('one_way', 'One-way (app → Google)'),
                            ('two_way', 'Two-way'),
                        ],
                        default='one_way',
                        max_length=16,
                    ),
                ),
                ('google_sync_token', models.TextField(blank=True, default='')),
                ('watch_channel_id', models.CharField(blank=True, default='', max_length=255)),
                ('watch_resource_id', models.CharField(blank=True, default='', max_length=255)),
                ('watch_channel_token', models.CharField(blank=True, default='', max_length=64)),
                ('watch_expiration', models.DateTimeField(blank=True, null=True)),
                ('last_synced_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'account',
                    models.ForeignKey(
                        db_column='account_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='google_calendar_integrations',
                        to='users.account',
                    ),
                ),
                (
                    'company',
                    models.ForeignKey(
                        db_column='company_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='google_calendar_integrations',
                        to='companies.company',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        db_column='created_by',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='google_calendar_integrations_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'google_calendar_integrations',
            },
        ),
        migrations.AddConstraint(
            model_name='googlecalendarintegration',
            constraint=models.UniqueConstraint(
                fields=('account', 'company'),
                name='google_calendar_integrations_one_per_company',
            ),
        ),
    ]
