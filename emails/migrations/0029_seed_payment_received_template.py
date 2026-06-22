from django.db import migrations

from planningwithyou.template_placeholders import (
    DEFAULT_PAYMENT_RECEIVED_BODY_HTML,
    DEFAULT_PAYMENT_RECEIVED_SUBJECT,
    EMAIL_TEMPLATE_PAYMENT_RECEIVED,
)


def seed_payment_received_per_company(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    EmailTemplate = apps.get_model('emails', 'EmailTemplate')

    for company in Company.objects.filter(deleted_at__isnull=True):
        exists = EmailTemplate.objects.filter(
            account_id=company.account_id,
            company_id=company.pk,
            name=EMAIL_TEMPLATE_PAYMENT_RECEIVED,
            template_type='quotations',
            deleted_at__isnull=True,
        ).exists()
        if exists:
            continue
        EmailTemplate.objects.create(
            account_id=company.account_id,
            company_id=company.pk,
            name=EMAIL_TEMPLATE_PAYMENT_RECEIVED,
            title='Payment Received',
            subject=DEFAULT_PAYMENT_RECEIVED_SUBJECT,
            body=DEFAULT_PAYMENT_RECEIVED_BODY_HTML,
            template_type='quotations',
            is_active=True,
            is_default=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0028_emaillog_quotation'),
        ('companies', '0011_ensure_main_company_per_account'),
    ]

    operations = [
        migrations.RunPython(seed_payment_received_per_company, migrations.RunPython.noop),
    ]
