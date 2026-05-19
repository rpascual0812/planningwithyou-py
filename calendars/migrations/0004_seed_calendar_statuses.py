from django.db import migrations

DEFAULT_CALENDAR_STATUSES = [
    ('Pending', '#ffffff', '#f0a830'),
    ('Confirmed', '#ffffff', '#52b585'),
    ('Follow-up', '#ffffff', '#5a8edb'),
    ('No Answer', '#ffffff', '#fd7e14'),
    ('On Hold', '#ffffff', '#9c6cd0'),
    ('Completed', '#ffffff', '#1f3a5f'),
    ('Declined', '#ffffff', '#d65a5a'),
]


def seed_calendar_statuses(apps, schema_editor):
    Account = apps.get_model('users', 'Account')
    CalendarStatus = apps.get_model('calendars', 'CalendarStatus')

    for account in Account.objects.all().iterator():
        existing_titles = set(
            CalendarStatus.objects.filter(account_id=account.id).values_list(
                'title',
                flat=True,
            ),
        )
        for sort_order, (title, text_color, background_color) in enumerate(
            DEFAULT_CALENDAR_STATUSES,
        ):
            if title in existing_titles:
                continue
            CalendarStatus.objects.create(
                account_id=account.id,
                title=title,
                description='',
                text_color=text_color,
                background_color=background_color,
                sort_order=sort_order,
                created_by_id=None,
            )


def unseed_calendar_statuses(apps, schema_editor):
    CalendarStatus = apps.get_model('calendars', 'CalendarStatus')
    titles = [row[0] for row in DEFAULT_CALENDAR_STATUSES]
    CalendarStatus.objects.filter(title__in=titles).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('calendars', '0003_calendar_booking'),
        ('users', '0015_user_company'),
    ]

    operations = [
        migrations.RunPython(seed_calendar_statuses, unseed_calendar_statuses),
    ]
