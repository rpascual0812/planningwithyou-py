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


def backfill_document_folders_company(apps, schema_editor):
    DocumentFolder = apps.get_model('documents', 'DocumentFolder')
    Company = apps.get_model('companies', 'Company')
    for folder in DocumentFolder.objects.filter(company_id__isnull=True).iterator():
        company_id = _main_company_id(Company, folder.account_id)
        if company_id is None:
            raise RuntimeError(
                f'Account {folder.account_id} has no company; create a company before migrating document folders.',
            )
        folder.company_id = company_id
        folder.save(update_fields=['company_id'])


def backfill_documents_company(apps, schema_editor):
    Document = apps.get_model('documents', 'Document')
    Company = apps.get_model('companies', 'Company')
    for doc in Document.objects.filter(company_id__isnull=True).iterator():
        company_id = _main_company_id(Company, doc.account_id)
        if company_id is None:
            raise RuntimeError(
                f'Account {doc.account_id} has no company; create a company before migrating documents.',
            )
        doc.company_id = company_id
        doc.save(update_fields=['company_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        ('documents', '0005_alter_document_account_alter_documentfolder_account'),
        ('users', '0015_user_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentfolder',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='document_folders',
                to='companies.company',
            ),
        ),
        migrations.RunPython(backfill_document_folders_company, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='documentfolder',
            name='company',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='document_folders',
                to='companies.company',
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='documents',
                to='companies.company',
            ),
        ),
        migrations.RunPython(backfill_documents_company, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='document',
            name='company',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='documents',
                to='companies.company',
            ),
        ),
    ]
