# Generated manually for scheduled appointment reminder emails.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendars', '0011_appointment_reminder'),
        ('companies', '0001_initial'),
        ('emails', '0029_seed_payment_received_template'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduledAppointmentReminder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_role', models.CharField(choices=[('contact', 'Contact'), ('author', 'Author')], max_length=16)),
                ('recipient_email', models.EmailField(max_length=255)),
                ('recipient_name', models.CharField(blank=True, default='', max_length=255)),
                ('send_at', models.DateTimeField(db_index=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], db_index=True, default='pending', max_length=16)),
                ('error', models.TextField(blank=True, default='')),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('account', models.ForeignKey(db_column='account_id', on_delete=django.db.models.deletion.CASCADE, related_name='scheduled_appointment_reminders', to='users.account')),
                ('appointment_reminder', models.ForeignKey(blank=True, db_column='appointment_reminder_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scheduled_sends', to='calendars.appointmentreminder')),
                ('calendar_event', models.ForeignKey(db_column='calendar_event_id', on_delete=django.db.models.deletion.CASCADE, related_name='scheduled_reminders', to='calendars.calendar')),
                ('company', models.ForeignKey(db_column='company_id', on_delete=django.db.models.deletion.CASCADE, related_name='scheduled_appointment_reminders', to='companies.company')),
                ('email_log', models.ForeignKey(blank=True, db_column='email_log_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scheduled_appointment_reminders', to='emails.emaillog')),
            ],
            options={
                'db_table': 'scheduled_appointment_reminders',
                'ordering': ['-send_at', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='scheduledappointmentreminder',
            index=models.Index(fields=['status', 'send_at'], name='sched_appt_rem_status_send'),
        ),
    ]
