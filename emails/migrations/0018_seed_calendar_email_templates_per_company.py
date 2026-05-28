from django.db import migrations

CALENDAR_TEMPLATES = [
    {
        'name': 'calendar_event_creation',
        'title': 'Scheduled Event',
        'subject': '{company_name} - Scheduled Event',
        'body': (
            '<p>Hi {first_name} {last_name},</p>'
            '<p>A new event has been scheduled:</p>'
            '<p>Title: {event_title}</p>'
            '<p>Start: {event_start}</p>'
            '<p>End: {event_end}</p>'
            '<p>Location: {event_location}</p>'
            '<p>Thank you.</p>'
        ),
    },
    {
        'name': 'calendar_event_updated',
        'title': 'Event Updated',
        'subject': '{company_name} - Event Updated',
        'body': (
            '<p>Hi {first_name} {last_name},</p>'
            '<p>An event has been updated:</p>'
            '<p>Title: {event_title}</p>'
            '<p>Start: {event_start}</p>'
            '<p>End: {event_end}</p>'
            '<p>Location: {event_location}</p>'
            '<p>Thank you.</p>'
        ),
    },
]


def seed_calendar_templates_per_company(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    EmailTemplate = apps.get_model('emails', 'EmailTemplate')

    for company in Company.objects.filter(deleted_at__isnull=True):
        for tpl in CALENDAR_TEMPLATES:
            exists = EmailTemplate.objects.filter(
                account_id=company.account_id,
                company_id=company.pk,
                name=tpl['name'],
                template_type='calendar',
                deleted_at__isnull=True,
            ).exists()
            if exists:
                continue
            EmailTemplate.objects.create(
                account_id=company.account_id,
                company_id=company.pk,
                name=tpl['name'],
                title=tpl['title'],
                subject=tpl['subject'],
                body=tpl['body'],
                template_type='calendar',
                is_active=True,
                is_default=True,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0017_alter_emaillog_company_nullable'),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            seed_calendar_templates_per_company,
            migrations.RunPython.noop,
        ),
    ]
