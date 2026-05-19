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


def backfill_tier_company(apps, schema_editor):
    Tier = apps.get_model('suppliers', 'Tier')
    Company = apps.get_model('companies', 'Company')

    for tier in Tier.objects.filter(company_id__isnull=True).iterator():
        company_id = _main_company_id(Company, tier.account_id)
        if company_id is None:
            raise RuntimeError(
                f'Account {tier.account_id} has no company; create a company before migrating tiers.',
            )
        tier.company_id = company_id
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
