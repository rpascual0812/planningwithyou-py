from django.db import migrations, models
import django.db.models.deletion


def set_accounts_country_philippines(apps, schema_editor):
    Account = apps.get_model('users', 'Account')
    Country = apps.get_model('countries', 'Country')
    philippines = Country.objects.filter(iso2_code='PH').first()
    if philippines is None:
        raise RuntimeError('Philippines (iso2_code=PH) not found in countries table.')
    Account.objects.update(country_id=philippines.id)


class Migration(migrations.Migration):

    dependencies = [
        ('countries', '0003_rebuild_countries_table'),
        ('users', '0009_remove_account_country_for_rebuild'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='country',
            field=models.ForeignKey(
                blank=True,
                db_column='country_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='accounts',
                to='countries.country',
            ),
        ),
        migrations.RunPython(
            set_accounts_country_philippines,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='account',
            name='country',
            field=models.ForeignKey(
                db_column='country_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='accounts',
                to='countries.country',
            ),
        ),
    ]
