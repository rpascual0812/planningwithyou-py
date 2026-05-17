import json
from pathlib import Path

from django.db import migrations, models


def seed_countries(apps, schema_editor):
    Country = apps.get_model('countries', 'Country')
    path = Path(__file__).resolve().parent.parent / 'data' / 'countries_seed.json'
    with path.open(encoding='utf-8') as handle:
        rows = json.load(handle)
    Country.objects.bulk_create(
        [Country(**row) for row in rows],
        batch_size=200,
    )


def unseed_countries(apps, schema_editor):
    Country = apps.get_model('countries', 'Country')
    Country.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('countries', '0002_rename_iso_code_iso2_code'),
        ('users', '0009_remove_account_country_for_rebuild'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Country',
        ),
        migrations.CreateModel(
            name='Country',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('iso_code', models.CharField(db_index=True, max_length=3, unique=True)),
                ('iso2_code', models.CharField(db_index=True, max_length=2, unique=True)),
                ('currency', models.CharField(max_length=128)),
                ('currency_symbol', models.CharField(max_length=16)),
                ('currency_code', models.CharField(db_index=True, max_length=3)),
            ],
            options={
                'db_table': 'countries',
                'ordering': ['name'],
            },
        ),
        migrations.RunPython(seed_countries, unseed_countries),
    ]
