from django.db import migrations


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


def backfill_formtemplate_company(apps, schema_editor):
    FormTemplate = apps.get_model('bookings', 'FormTemplate')
    Company = apps.get_model('companies', 'Company')

    account_ids = (
        FormTemplate.objects.filter(company_id__isnull=True)
        .values_list('account_id', flat=True)
        .distinct()
    )
    for account_id in account_ids:
        company_id = _main_company_id(Company, account_id)
        if company_id is None:
            continue
        FormTemplate.objects.filter(
            account_id=account_id,
            company_id__isnull=True,
        ).update(company_id=company_id)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0057_remove_quotation_bookings_account_unique_id_uniq_and_more'),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            backfill_formtemplate_company,
            migrations.RunPython.noop,
        ),
    ]
