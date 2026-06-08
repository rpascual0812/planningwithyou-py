from collections import defaultdict

from django.db import migrations, models
import django.db.models.deletion


def _ensure_main_company_id(apps, account_id):
    Company = apps.get_model('companies', 'Company')
    company = (
        Company.objects.filter(
            account_id=account_id,
            is_main=True,
            deleted_at__isnull=True,
        )
        .order_by('id')
        .first()
    )
    if company is not None:
        return company.id
    company = (
        Company.objects.filter(
            account_id=account_id,
            deleted_at__isnull=True,
        )
        .order_by('sort_order', 'name', 'id')
        .first()
    )
    if company is not None:
        return company.id

    Account = apps.get_model('users', 'Account')
    account = Account.objects.filter(pk=account_id).first()
    name = (account.name if account else None) or f'Account {account_id}'
    create_kwargs = {
        'account_id': account_id,
        'name': name,
        'is_main': True,
        'is_active': True,
    }
    if any(field.name == 'supplier_type' for field in Company._meta.get_fields()):
        supplier_type_id = getattr(account, 'supplier_type_id', None) if account else None
        create_kwargs['supplier_type_id'] = supplier_type_id or 1
    company = Company.objects.create(**create_kwargs)
    return company.id


def backfill_booking_companies(apps, schema_editor):
    BookingItem = apps.get_model('bookings', 'BookingItem')
    for item in BookingItem.objects.filter(company_id__isnull=True).iterator():
        item.company_id = _ensure_main_company_id(apps, item.account_id)
        item.save(update_fields=['company_id'])


def backfill_sequence_companies(apps, schema_editor):
    BookingUniqueIdSequence = apps.get_model('bookings', 'BookingUniqueIdSequence')
    for seq in BookingUniqueIdSequence.objects.filter(company_id__isnull=True).iterator():
        seq.company_id = _ensure_main_company_id(apps, seq.account_id)
        seq.save(update_fields=['company_id'])


def merge_duplicate_sequence_rows(apps, schema_editor):
    BookingUniqueIdSequence = apps.get_model('bookings', 'BookingUniqueIdSequence')
    grouped: dict[tuple[int, int], list] = defaultdict(list)
    for seq in BookingUniqueIdSequence.objects.all().iterator():
        if seq.company_id:
            grouped[(seq.company_id, seq.year)].append(seq)

    for rows in grouped.values():
        if len(rows) <= 1:
            continue
        keep = max(rows, key=lambda row: row.last_sequence)
        for row in rows:
            if row.pk != keep.pk:
                row.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0028_ensure_booking_created_by_column'),
        ('companies', '0002_company_supplier_type'),
        ('users', '0015_user_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingitem',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='bookings',
                to='companies.company',
            ),
        ),
        migrations.RunPython(backfill_booking_companies, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='bookingitem',
            name='company',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='bookings',
                to='companies.company',
            ),
        ),
        migrations.RemoveConstraint(
            model_name='bookingitem',
            name='bookings_account_unique_id_uniq',
        ),
        migrations.AddConstraint(
            model_name='bookingitem',
            constraint=models.UniqueConstraint(
                fields=('company', 'unique_id'),
                name='bookings_company_unique_id_uniq',
            ),
        ),
        migrations.AddField(
            model_name='bookinguniqueidsequence',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='+',
                to='companies.company',
            ),
        ),
        migrations.RunPython(backfill_sequence_companies, migrations.RunPython.noop),
        migrations.RunPython(merge_duplicate_sequence_rows, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='bookinguniqueidsequence',
            name='company',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='+',
                to='companies.company',
            ),
        ),
        migrations.RemoveConstraint(
            model_name='bookinguniqueidsequence',
            name='booking_unique_id_seq_account_year_uniq',
        ),
        migrations.AddConstraint(
            model_name='bookinguniqueidsequence',
            constraint=models.UniqueConstraint(
                fields=('company', 'year'),
                name='booking_unique_id_seq_company_year_uniq',
            ),
        ),
    ]
