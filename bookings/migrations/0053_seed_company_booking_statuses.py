from django.db import migrations

# Keep in sync with users.registration.BOOKING_STATUSES
DEFAULT_BOOKING_STATUSES = [
    ('New', '#1f3a5f'),
    ('Confirmed', '#52b585'),
    ('In-progress', '#5a8edb'),
    ('Completed', '#3a9870'),
    ('Cancelled', '#d65a5a'),
]


def _ensure_company_statuses(Company, BookingStatus, company):
    account_id = company.account_id
    company_id = company.id
    for sort_order, (title, color) in enumerate(DEFAULT_BOOKING_STATUSES):
        if BookingStatus.objects.filter(
            account_id=account_id,
            company_id=company_id,
            title__iexact=title,
        ).exists():
            continue
        BookingStatus.objects.create(
            account_id=account_id,
            company_id=company_id,
            title=title,
            color=color,
            sort_order=sort_order,
        )


def _status_for_company(BookingStatus, account_id, company_id, title):
    return BookingStatus.objects.filter(
        account_id=account_id,
        company_id=company_id,
        title__iexact=title,
    ).first()


def seed_and_migrate_booking_statuses(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    BookingStatus = apps.get_model('bookings', 'BookingStatus')
    BookingItem = apps.get_model('bookings', 'BookingItem')

    companies = Company.objects.filter(deleted_at__isnull=True).order_by('id')
    for company in companies.iterator():
        _ensure_company_statuses(Company, BookingStatus, company)

    legacy_statuses = list(
        BookingStatus.objects.filter(company_id__isnull=True).order_by('id'),
    )
    if not legacy_statuses:
        return

    for item in BookingItem.objects.select_related('status').iterator():
        old_status = item.status
        if old_status is None:
            continue
        new_status = _status_for_company(
            BookingStatus,
            item.account_id,
            item.company_id,
            old_status.title,
        )
        if new_status is None:
            _ensure_company_statuses(
                Company,
                BookingStatus,
                Company.objects.get(pk=item.company_id),
            )
            new_status = _status_for_company(
                BookingStatus,
                item.account_id,
                item.company_id,
                old_status.title,
            )
        if new_status is not None and item.status_id != new_status.pk:
            item.status_id = new_status.pk
            item.save(update_fields=['status_id'])

    with schema_editor.connection.cursor() as cursor:
        for legacy in legacy_statuses:
            cursor.execute(
                'SELECT tag_id FROM booking_statuses_tags '
                'WHERE bookingstatus_id = %s',
                [legacy.pk],
            )
            tag_ids = [row[0] for row in cursor.fetchall()]
            if not tag_ids:
                continue
            account_companies = Company.objects.filter(
                account_id=legacy.account_id,
                deleted_at__isnull=True,
            )
            for company in account_companies.iterator():
                mapped = _status_for_company(
                    BookingStatus,
                    legacy.account_id,
                    company.id,
                    legacy.title,
                )
                if mapped is None:
                    continue
                for tag_id in tag_ids:
                    cursor.execute(
                        'SELECT 1 FROM booking_statuses_tags '
                        'WHERE bookingstatus_id = %s AND tag_id = %s',
                        [mapped.pk, tag_id],
                    )
                    if cursor.fetchone():
                        continue
                    cursor.execute(
                        'INSERT INTO booking_statuses_tags '
                        '(bookingstatus_id, tag_id) VALUES (%s, %s)',
                        [mapped.pk, tag_id],
                    )

    BookingStatus.objects.filter(company_id__isnull=True).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0052_bookingstatus_company'),
    ]

    # Data migration only: PostgreSQL rejects ALTER TABLE in the same
    # transaction as row updates that enqueue trigger events.
    atomic = False

    operations = [
        migrations.RunPython(
            seed_and_migrate_booking_statuses,
            noop_reverse,
        ),
    ]
