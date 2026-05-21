from django.db import migrations

from planningwithyou.template_placeholders import (
    DEFAULT_PAYMENT_LINK_BODY_HTML,
    DEFAULT_PAYMENT_LINK_SUBJECT,
    EMAIL_TEMPLATE_PAYMENT_LINK,
)


def seed_payment_link_templates(apps, schema_editor):
    Account = apps.get_model('users', 'Account')
    EmailTemplate = apps.get_model('emails', 'EmailTemplate')

    for account in Account.objects.filter(deleted_at__isnull=True):
        exists = EmailTemplate.objects.filter(
            account_id=account.pk,
            name=EMAIL_TEMPLATE_PAYMENT_LINK,
            template_type='bookings',
            deleted_at__isnull=True,
        ).exists()
        if exists:
            continue
        EmailTemplate.objects.create(
            account_id=account.pk,
            company_id=None,
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
        ('emails', '0014_emailtemplate_is_default'),
        ('users', '0012_alter_account_logo_charfield'),
    ]

    operations = [
        migrations.RunPython(seed_payment_link_templates, migrations.RunPython.noop),
    ]
