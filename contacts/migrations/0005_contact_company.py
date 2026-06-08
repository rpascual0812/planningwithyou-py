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


def backfill_contacts_company(apps, schema_editor):
    Contact = apps.get_model('contacts', 'Contact')
    for contact in Contact.objects.filter(company_org_id__isnull=True).iterator():
        contact.company_org_id = _ensure_main_company_id(apps, contact.account_id)
        contact.save(update_fields=['company_org_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_company_supplier_type'),
        ('contacts', '0004_contactnumber_is_default_contactaddress_is_default'),
        ('users', '0015_user_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='company_org',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='contacts',
                to='companies.company',
            ),
        ),
        migrations.RunPython(backfill_contacts_company, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='contact',
            name='company_org',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='contacts',
                to='companies.company',
            ),
        ),
    ]
