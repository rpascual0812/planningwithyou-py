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


def backfill_user_companies(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Company = apps.get_model('companies', 'Company')
    for user in User.objects.filter(company_id__isnull=True).iterator():
        company_id = _main_company_id(Company, user.account_id)
        if company_id is None:
            raise RuntimeError(
                f'Account {user.account_id} has no company; create a company before migrating users.',
            )
        user.company_id = company_id
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
