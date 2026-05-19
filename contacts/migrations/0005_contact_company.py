from django.db import migrations, models
import django.db.models.deletion


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


def backfill_contacts_company(apps, schema_editor):
    Contact = apps.get_model('contacts', 'Contact')
    Company = apps.get_model('companies', 'Company')
    for contact in Contact.objects.filter(company_org_id__isnull=True).iterator():
        company_id = _main_company_id(Company, contact.account_id)
        if company_id is None:
            raise RuntimeError(
                f'Account {contact.account_id} has no company; create a company before migrating contacts.',
            )
        contact.company_org_id = company_id
        contact.save(update_fields=['company_org_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
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
