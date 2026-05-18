from collections import defaultdict

from django.db import migrations, models
import django.db.models.deletion


def backfill_unique_ids(apps, schema_editor):
    BookingItem = apps.get_model('bookings', 'BookingItem')
    BookingUniqueIdSequence = apps.get_model('bookings', 'BookingUniqueIdSequence')

    counters: dict[tuple[int, int], int] = defaultdict(int)
    max_by_year: dict[tuple[int, int], int] = defaultdict(int)

    items = BookingItem.objects.order_by('account_id', 'created_at', 'id')
    for item in items.iterator():
        created = item.created_at
        year = created.year if created else 2000
        account_id = item.account_id
        counters[(account_id, year)] += 1
        seq = counters[(account_id, year)]
        item.unique_id = f'{year % 100:02d}-{seq:04d}'
        item.save(update_fields=['unique_id'])
        max_by_year[(account_id, year)] = seq

    for (account_id, year), last_sequence in max_by_year.items():
        BookingUniqueIdSequence.objects.update_or_create(
            account_id=account_id,
            year=year,
            defaults={'last_sequence': last_sequence},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0021_rename_booking_columns_to_statuses'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookingUniqueIdSequence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.PositiveSmallIntegerField()),
                ('last_sequence', models.PositiveIntegerField(default=0)),
                (
                    'account',
                    models.ForeignKey(
                        db_column='account_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='+',
                        to='users.account',
                    ),
                ),
            ],
            options={
                'db_table': 'booking_unique_id_sequences',
            },
        ),
        migrations.AddConstraint(
            model_name='bookinguniqueidsequence',
            constraint=models.UniqueConstraint(
                fields=('account', 'year'),
                name='booking_unique_id_seq_account_year_uniq',
            ),
        ),
        migrations.AddField(
            model_name='bookingitem',
            name='unique_id',
            field=models.CharField(max_length=7, null=True),
        ),
        migrations.RunPython(backfill_unique_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='bookingitem',
            name='unique_id',
            field=models.CharField(max_length=7),
        ),
        migrations.AddConstraint(
            model_name='bookingitem',
            constraint=models.UniqueConstraint(
                fields=('account', 'unique_id'),
                name='bookings_account_unique_id_uniq',
            ),
        ),
    ]
