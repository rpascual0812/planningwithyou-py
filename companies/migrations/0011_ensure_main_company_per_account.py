from django.db import migrations


def ensure_main_company_per_account(apps, schema_editor):
    Account = apps.get_model('users', 'Account')
    Company = apps.get_model('companies', 'Company')

    for account in Account.objects.all().iterator():
        company = (
            Company.objects.filter(
                account_id=account.id,
                is_main=True,
                deleted_at__isnull=True,
            )
            .order_by('id')
            .first()
        )
        if company is None:
            company = (
                Company.objects.filter(
                    account_id=account.id,
                    deleted_at__isnull=True,
                )
                .order_by('sort_order', 'name', 'id')
                .first()
            )
        if company is not None:
            continue

        supplier_type_id = getattr(account, 'supplier_type_id', None) or 1
        Company.objects.create(
            account_id=account.id,
            name=account.name or f'Account {account.id}',
            is_main=True,
            is_active=True,
            supplier_type_id=supplier_type_id,
        )


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('companies', '0010_company_contact_email'),
        ('users', '0015_user_company'),
    ]

    operations = [
        migrations.RunPython(
            ensure_main_company_per_account,
            migrations.RunPython.noop,
        ),
    ]
