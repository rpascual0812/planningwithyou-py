import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0003_company_contact_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyKybVerification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('business_type', models.CharField(blank=True, choices=[('sole_proprietor', 'Sole proprietorship'), ('corporation', 'Corporation')], default='', max_length=32)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted for review'), ('approved', 'Approved'), ('rejected', 'Rejected')], db_index=True, default='draft', max_length=20)),
                ('government_id_file', models.CharField(blank=True, default='', help_text='Stored file reference for valid government ID.', max_length=512)),
                ('dti_registration_file', models.CharField(blank=True, default='', max_length=512)),
                ('sole_prop_business_address', models.TextField(blank=True, default='')),
                ('sole_prop_mobile_number', models.CharField(blank=True, default='', max_length=63)),
                ('bank_account_same_name', models.TextField(blank=True, default='', help_text='Bank account details; account must be under the same legal name.')),
                ('sec_registration_file', models.CharField(blank=True, default='', max_length=512)),
                ('articles_of_incorporation_file', models.CharField(blank=True, default='', max_length=512)),
                ('bir_registration_file', models.CharField(blank=True, default='', max_length=512)),
                ('owner_director_id_files', models.JSONField(blank=True, default=list, help_text='List of file references for valid IDs of owners/directors.')),
                ('business_website_social', models.TextField(blank=True, default='', help_text='Business website and/or social media pages.')),
                ('company_email_domain', models.CharField(blank=True, default='', max_length=255)),
                ('selfie_verification_file', models.CharField(blank=True, default='', max_length=512)),
                ('proof_of_address_file', models.CharField(blank=True, default='', max_length=512)),
                ('business_description', models.TextField(blank=True, default='')),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('rejection_notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(db_column='company_id', on_delete=django.db.models.deletion.CASCADE, related_name='kyb_verification', to='companies.company')),
                ('reviewed_by', models.ForeignKey(blank=True, db_column='reviewed_by', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='company_kyb_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'company_kyb_verifications',
                'ordering': ['-updated_at'],
            },
        ),
    ]
