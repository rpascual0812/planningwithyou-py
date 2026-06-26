from django.db import migrations

REMINDER_TEMPLATE = {
    'name': 'calendar_event_reminder',
    'title': 'Appointment Reminder',
    'subject': '{company_name} - Appointment reminder for {event_title}',
    'body': (
        '<p>Hi {first_name} {last_name},</p>'
        '<p>This is a reminder about your upcoming appointment:</p>'
        '<p>Title: {event_title}</p>'
        '<p>Date: {event_date}</p>'
        '<p>Time: {event_time}</p>'
        '<p>Location: {event_location}</p>'
        '<p>Thank you.</p>'
    ),
}


def seed_calendar_reminder_template(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    EmailTemplate = apps.get_model('emails', 'EmailTemplate')

    for company in Company.objects.filter(deleted_at__isnull=True):
        exists = EmailTemplate.objects.filter(
            account_id=company.account_id,
            company_id=company.pk,
            name=REMINDER_TEMPLATE['name'],
            template_type='calendar',
            deleted_at__isnull=True,
        ).exists()
        if exists:
            continue
        EmailTemplate.objects.create(
            account_id=company.account_id,
            company_id=company.pk,
            name=REMINDER_TEMPLATE['name'],
            title=REMINDER_TEMPLATE['title'],
            subject=REMINDER_TEMPLATE['subject'],
            body=REMINDER_TEMPLATE['body'],
            template_type='calendar',
            is_active=True,
            is_default=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0029_seed_payment_received_template'),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_calendar_reminder_template, migrations.RunPython.noop),
    ]
