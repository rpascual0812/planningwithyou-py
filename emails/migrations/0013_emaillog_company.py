import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


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


def backfill_email_log_companies(apps, schema_editor):
    EmailLog = apps.get_model('emails', 'EmailLog')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))

    user_company_by_id = {
        row['id']: row['company_id']
        for row in User.objects.values('id', 'company_id')
    }
    main_by_account: dict[int, int] = {}

    for log in EmailLog.objects.filter(company_id__isnull=True).iterator():
        company_id = None
        if log.created_by_id:
            company_id = user_company_by_id.get(log.created_by_id)
        if company_id is None:
            if log.account_id not in main_by_account:
                main_by_account[log.account_id] = _ensure_main_company_id(apps, log.account_id)
            company_id = main_by_account[log.account_id]
        log.company_id = company_id
        log.save(update_fields=['company_id'])


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('companies', '0002_company_supplier_type'),
        ('emails', '0012_emailtemplate_company'),
        ('users', '0015_user_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='emaillog',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='email_logs',
                to='companies.company',
            ),
        ),
        migrations.RunPython(backfill_email_log_companies, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='emaillog',
            name='company',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='email_logs',
                to='companies.company',
            ),
        ),
    ]
