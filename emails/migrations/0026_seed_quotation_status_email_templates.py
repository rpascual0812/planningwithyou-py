from django.db import migrations

STATUS_CONTACT_TEMPLATE = {
    'name': 'quotation_status_contact',
    'title': 'Quotation Status (Contact)',
    'subject': '{company_name} – Quotation {quotation_unique_id} is now {status_title}',
    'body': (
        '<p>Hi {first_name} {last_name},</p>'
        '<p>Your quotation <strong>{quotation_title}</strong> ({quotation_unique_id}) '
        'has been updated from <strong>{previous_status}</strong> to '
        '<strong>{status_title}</strong>.</p>'
        '<p>Thank you,<br>{company_name}</p>'
    ),
}

STATUS_COMPANY_TEMPLATE = {
    'name': 'quotation_status_company',
    'title': 'Quotation Status (Company)',
    'subject': 'Quotation {quotation_unique_id} moved to {status_title}',
    'body': (
        '<p>Hello,</p>'
        '<p>Quotation <strong>{quotation_title}</strong> ({quotation_unique_id}) '
        'has been updated from <strong>{previous_status}</strong> to '
        '<strong>{status_title}</strong>.</p>'
        '<p>Thank you.</p>'
    ),
}


def seed_quotation_status_templates_per_company(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    EmailTemplate = apps.get_model('emails', 'EmailTemplate')

    for company in Company.objects.filter(deleted_at__isnull=True):
        for template in (STATUS_CONTACT_TEMPLATE, STATUS_COMPANY_TEMPLATE):
            exists = EmailTemplate.objects.filter(
                account_id=company.account_id,
                company_id=company.pk,
                name=template['name'],
                template_type='quotations',
                deleted_at__isnull=True,
            ).exists()
            if exists:
                continue
            EmailTemplate.objects.create(
                account_id=company.account_id,
                company_id=company.pk,
                name=template['name'],
                title=template['title'],
                subject=template['subject'],
                body=template['body'],
                template_type='quotations',
                is_active=True,
                is_default=True,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0025_alter_emailtemplate_template_type'),
        ('companies', '0011_ensure_main_company_per_account'),
    ]

    operations = [
        migrations.RunPython(
            seed_quotation_status_templates_per_company,
            migrations.RunPython.noop,
        ),
    ]
