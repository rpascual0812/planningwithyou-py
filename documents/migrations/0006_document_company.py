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


def backfill_document_folders_company(apps, schema_editor):
    DocumentFolder = apps.get_model('documents', 'DocumentFolder')
    for folder in DocumentFolder.objects.filter(company_id__isnull=True).iterator():
        folder.company_id = _ensure_main_company_id(apps, folder.account_id)
        folder.save(update_fields=['company_id'])


def backfill_documents_company(apps, schema_editor):
    Document = apps.get_model('documents', 'Document')
    for doc in Document.objects.filter(company_id__isnull=True).iterator():
        doc.company_id = _ensure_main_company_id(apps, doc.account_id)
        doc.save(update_fields=['company_id'])


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('companies', '0011_ensure_main_company_per_account'),
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
