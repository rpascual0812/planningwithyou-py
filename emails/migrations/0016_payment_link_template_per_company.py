from django.db import migrations

from planningwithyou.template_placeholders import (
    DEFAULT_PAYMENT_LINK_BODY_HTML,
    DEFAULT_PAYMENT_LINK_SUBJECT,
    EMAIL_TEMPLATE_PAYMENT_LINK,
)


def seed_payment_link_per_company(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    EmailTemplate = apps.get_model('emails', 'EmailTemplate')

    for company in Company.objects.filter(deleted_at__isnull=True):
        exists = EmailTemplate.objects.filter(
            account_id=company.account_id,
            company_id=company.pk,
            name=EMAIL_TEMPLATE_PAYMENT_LINK,
            template_type='bookings',
            deleted_at__isnull=True,
        ).exists()
        if exists:
            continue
        EmailTemplate.objects.create(
            account_id=company.account_id,
            company_id=company.pk,
            name=EMAIL_TEMPLATE_PAYMENT_LINK,
            title='Payment link',
            subject=DEFAULT_PAYMENT_LINK_SUBJECT,
            body=DEFAULT_PAYMENT_LINK_BODY_HTML,
            template_type='bookings',
            is_active=True,
            is_default=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0015_seed_payment_link_email_template'),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_payment_link_per_company, migrations.RunPython.noop),
    ]
