from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import migrations


LOGO_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif')


def _api_logo_url(company_id: int) -> str:
    base = getattr(settings, 'API_PUBLIC_BASE_URL', '').strip().rstrip('/')
    if not base:
        base = 'http://localhost:8000'
    return f'{base}/api/files/c/{company_id}/logo/'


def migrate_account_logos_to_companies(apps, schema_editor):
    Account = apps.get_model('users', 'Account')
    Company = apps.get_model('companies', 'Company')

    for account in Account.objects.all():
        company = (
            Company.objects.filter(account_id=account.pk, is_main=True)
            .order_by('id')
            .first()
        )
        if company is None:
            company = (
                Company.objects.filter(account_id=account.pk)
                .order_by('sort_order', 'id')
                .first()
            )
        if company is None:
            create_kwargs = {
                'account_id': account.pk,
                'name': account.name or f'Account {account.pk}',
                'is_main': True,
                'is_active': True,
            }
            if any(field.name == 'supplier_type' for field in Company._meta.get_fields()):
                create_kwargs['supplier_type_id'] = account.supplier_type_id or 1
            company = Company.objects.create(**create_kwargs)

        src_key = ''
        for ext in LOGO_EXTENSIONS:
            key = f'account_logos/{account.pk}/logo{ext}'
            if default_storage.exists(key):
                src_key = key
                break

        logo_field = (getattr(account, 'logo', None) or '').strip()
        if not src_key and not logo_field:
            continue

        if src_key:
            ext = Path(src_key).suffix.lower() or '.png'
            dest = f'company_logos/{account.pk}/{company.pk}/logo{ext}'
            if not default_storage.exists(dest):
                with default_storage.open(src_key, 'rb') as handle:
                    default_storage.save(dest, ContentFile(handle.read()))

        company.logo = _api_logo_url(company.pk)
        company.save(update_fields=['logo'])


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        ('users', '0012_alter_account_logo_charfield'),
    ]

    operations = [
        migrations.RunPython(
            migrate_account_logos_to_companies,
            migrations.RunPython.noop,
        ),
    ]
