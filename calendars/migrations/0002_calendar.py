from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('calendars', '0001_initial'),
        ('companies', '0001_initial'),
        ('contacts', '0005_contact_company'),
        ('users', '0015_user_company'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Calendar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('start', models.DateTimeField()),
                ('end', models.DateTimeField()),
                ('repeat_type', models.CharField(blank=True, max_length=32, null=True)),
                ('repeat_end', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                (
                    'account',
                    models.ForeignKey(
                        db_column='account_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='+',
                        to='users.account',
                    ),
                ),
                (
                    'company',
                    models.ForeignKey(
                        db_column='company_id',
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='calendar_events',
                        to='companies.company',
                    ),
                ),
                (
                    'contact',
                    models.ForeignKey(
                        blank=True,
                        db_column='contact_id',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='calendar_events',
                        to='contacts.contact',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        db_column='created_by',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='calendar_events_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'status',
                    models.ForeignKey(
                        db_column='status_id',
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='events',
                        to='calendars.calendarstatus',
                    ),
                ),
            ],
            options={
                'db_table': 'calendar',
                'ordering': ['start', 'id'],
            },
        ),
    ]
