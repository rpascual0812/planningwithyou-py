import django.db.models.deletion
from django.db import migrations, models


def assign_configs_to_first_account(apps, schema_editor):
    Config = apps.get_model('config', 'Config')
    Account = apps.get_model('users', 'Account')
    account = Account.objects.order_by('id').first()
    if account is None:
        Config.objects.all().delete()
        return
    Config.objects.update(account_id=account.id)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_account_country_after_rebuild'),
        ('config', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='config',
            name='account',
            field=models.ForeignKey(
                db_column='account_id',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='configs',
                to='users.account',
            ),
        ),
        migrations.RunPython(
            assign_configs_to_first_account,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='config',
            name='account',
            field=models.ForeignKey(
                db_column='account_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='configs',
                to='users.account',
            ),
        ),
        migrations.AddConstraint(
            model_name='config',
            constraint=models.UniqueConstraint(
                fields=('account', 'scope', 'name'),
                name='config_account_scope_name_uniq',
            ),
        ),
    ]
