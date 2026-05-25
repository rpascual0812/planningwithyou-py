from django.db import migrations


def sync_is_active_from_status(apps, schema_editor):
    Account = apps.get_model('users', 'Account')
    for account in Account.objects.all().only('id', 'status', 'is_active'):
        if (account.status or '').strip().lower() != 'active':
            Account.objects.filter(pk=account.pk).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0017_account_paymongo_customer_id'),
    ]

    operations = [
        migrations.RunPython(sync_is_active_from_status, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='account',
            name='status',
        ),
    ]
