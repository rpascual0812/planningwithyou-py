from django.db import migrations

KYB_VERIFIED_TEMPLATE = {
    'name': 'kyb_verified',
    'title': 'Business verification approved',
    'subject': 'Your business verification is approved – {company_name}',
    'body': (
        '<h3>Hello,</h3>'
        '<p>Your Know Your Business (KYB) verification for '
        '<strong>{company_name}</strong> has been approved.</p>'
        '<p>You can now accept live payments through Planning With You.</p>'
        '<p>If you have questions, reply to this email.</p>'
        '<p>Thank you,<br>{company_name}</p>'
    ),
}


def seed_kyb_verified_template_per_company(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    EmailTemplate = apps.get_model('emails', 'EmailTemplate')

    for company in Company.objects.filter(deleted_at__isnull=True):
        exists = EmailTemplate.objects.filter(
            account_id=company.account_id,
            company_id=company.pk,
            name=KYB_VERIFIED_TEMPLATE['name'],
            template_type='users',
            deleted_at__isnull=True,
        ).exists()
        if exists:
            continue
        EmailTemplate.objects.create(
            account_id=company.account_id,
            company_id=company.pk,
            name=KYB_VERIFIED_TEMPLATE['name'],
            title=KYB_VERIFIED_TEMPLATE['title'],
            subject=KYB_VERIFIED_TEMPLATE['subject'],
            body=KYB_VERIFIED_TEMPLATE['body'],
            template_type='users',
            is_active=True,
            is_default=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0020_gmail_integration'),
        ('companies', '0010_company_contact_email'),
    ]

    operations = [
        migrations.RunPython(
            seed_kyb_verified_template_per_company,
            migrations.RunPython.noop,
        ),
    ]
