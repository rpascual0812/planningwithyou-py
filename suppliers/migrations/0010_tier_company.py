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
    company = Company.objects.create(
        account_id=account_id,
        name=name,
        is_main=True,
        is_active=True,
    )
    return company.id


def backfill_tier_company(apps, schema_editor):
    Tier = apps.get_model('suppliers', 'Tier')

    for tier in Tier.objects.filter(company_id__isnull=True).iterator():
        tier.company_id = _ensure_main_company_id(apps, tier.account_id)
        tier.save(update_fields=['company_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_company_supplier_type'),
        ('suppliers', '0009_supplier_setting_company_supplier'),
    ]

    operations = [
        migrations.AddField(
            model_name='tier',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name='tiers',
                to='companies.company',
            ),
        ),
        migrations.RunPython(backfill_tier_company, noop),
        migrations.AlterField(
            model_name='tier',
            name='company',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=models.deletion.CASCADE,
                related_name='tiers',
                to='companies.company',
            ),
        ),
    ]
