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


def backfill_user_companies(apps, schema_editor):
    User = apps.get_model('users', 'User')
    for user in User.objects.filter(company_id__isnull=True).iterator():
        user.company_id = _ensure_main_company_id(apps, user.account_id)
        user.save(update_fields=['company_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        ('users', '0014_remove_account_logo'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='users',
                to='companies.company',
            ),
        ),
        migrations.RunPython(backfill_user_companies, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='company',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='users',
                to='companies.company',
            ),
        ),
    ]
