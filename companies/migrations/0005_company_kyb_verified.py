from django.db import migrations, models


def backfill_kyb_verified(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    CompanyKybVerification = apps.get_model('companies', 'CompanyKybVerification')
    approved_company_ids = CompanyKybVerification.objects.filter(
        status='approved',
    ).values_list('company_id', flat=True)
    if approved_company_ids:
        Company.objects.filter(pk__in=approved_company_ids).update(kyb_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0004_company_kyb_verification'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='kyb_verified',
            field=models.BooleanField(
                default=False,
                help_text='Set when KYB verification is approved; required for live payments.',
            ),
        ),
        migrations.RunPython(backfill_kyb_verified, migrations.RunPython.noop),
    ]
