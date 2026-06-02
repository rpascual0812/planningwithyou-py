from django.conf import settings
from django.db import migrations, models


def backfill_company_contact_email(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    User = apps.get_model('users', 'User')
    for company in Company.objects.all().iterator():
        if (company.contact_email or '').strip():
            continue
        email = (
            User.objects.filter(company_id=company.id)
            .order_by('id')
            .values_list('email', flat=True)
            .first()
        )
        if not email:
            continue
        Company.objects.filter(pk=company.pk).update(contact_email=email)


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0009_kyb_business_type_choices'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='contact_email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
        migrations.RunPython(backfill_company_contact_email, migrations.RunPython.noop),
    ]
