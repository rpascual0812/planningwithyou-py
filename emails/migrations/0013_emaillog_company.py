import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _main_company_id(Company, account_id):
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
    return company.id if company else None


def backfill_email_log_companies(apps, schema_editor):
    EmailLog = apps.get_model('emails', 'EmailLog')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    Company = apps.get_model('companies', 'Company')

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
                main_by_account[log.account_id] = _main_company_id(Company, log.account_id)
            company_id = main_by_account[log.account_id]
        if company_id is None:
            raise RuntimeError(
                f'Account {log.account_id} has no company; create a company before migrating email logs.',
            )
        log.company_id = company_id
        log.save(update_fields=['company_id'])


class Migration(migrations.Migration):

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
