import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0014_rename_companykybverification_status_paymongo_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('calendars', '0010_google_calendar_integration_created_at_backfill'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppointmentReminder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('calendar', models.CharField(
                    choices=[('start', 'Before event start'), ('end', 'Before event end')],
                    default='start',
                    help_text='Which calendar event time the offset is measured from.',
                    max_length=16,
                )),
                ('frequency', models.PositiveIntegerField(default=1)),
                ('unit', models.CharField(
                    choices=[
                        ('minute', 'Minute'),
                        ('minutes', 'Minutes'),
                        ('hour', 'Hour'),
                        ('hours', 'Hours'),
                        ('day', 'Day'),
                        ('days', 'Days'),
                        ('week', 'Week'),
                        ('weeks', 'Weeks'),
                    ],
                    default='hours',
                    max_length=16,
                )),
                ('reminder_type', models.CharField(
                    choices=[('email', 'Email'), ('sms', 'SMS')],
                    db_column='type',
                    default='email',
                    max_length=8,
                )),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(null=True, blank=True)),
                ('account', models.ForeignKey(
                    db_column='account_id',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='appointment_reminders',
                    to='users.account',
                )),
                ('company', models.ForeignKey(
                    db_column='company_id',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='appointment_reminders',
                    to='companies.company',
                )),
                ('created_by', models.ForeignKey(
                    blank=True,
                    db_column='created_by',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='appointment_reminders_created',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('calendar_statuses', models.ManyToManyField(
                    blank=True,
                    related_name='appointment_reminders',
                    to='calendars.calendarstatus',
                )),
            ],
            options={
                'db_table': 'appointment_reminders',
                'ordering': ['id'],
            },
        ),
    ]
