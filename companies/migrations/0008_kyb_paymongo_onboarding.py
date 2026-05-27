from django.db import migrations, models


def submitted_to_pending_paymongo(apps, schema_editor):
    CompanyKybVerification = apps.get_model('companies', 'CompanyKybVerification')
    CompanyKybVerification.objects.filter(status='submitted').update(
        status='pending_paymongo',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0007_company_max_bookings_per_day'),
    ]

    operations = [
        migrations.AddField(
            model_name='companykybverification',
            name='paymongo_merchant_id',
            field=models.CharField(
                blank=True,
                default='',
                help_text='PayMongo platform merchant / child account id.',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='companykybverification',
            name='onboarding_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='PayMongo-hosted onboarding link for document upload and KYC.',
                max_length=2048,
            ),
        ),
        migrations.AddField(
            model_name='companykybverification',
            name='merchant_business_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='companykybverification',
            name='merchant_email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
        migrations.AddField(
            model_name='companykybverification',
            name='merchant_mobile_number',
            field=models.CharField(blank=True, default='', max_length=63),
        ),
        migrations.AddField(
            model_name='companykybverification',
            name='bank_details',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Optional payout bank details collected before PayMongo onboarding.',
            ),
        ),
        migrations.AddField(
            model_name='companykybverification',
            name='business_website',
            field=models.URLField(blank=True, default='', max_length=2048),
        ),
        migrations.AlterField(
            model_name='companykybverification',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('pending_paymongo', 'Pending PayMongo verification'),
                    ('approved', 'Verified'),
                    ('rejected', 'Rejected'),
                ],
                db_index=True,
                default='draft',
                max_length=32,
            ),
        ),
        migrations.RunPython(submitted_to_pending_paymongo, migrations.RunPython.noop),
    ]
