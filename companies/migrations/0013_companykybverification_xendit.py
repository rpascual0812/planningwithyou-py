from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0012_company_business_legal_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='companykybverification',
            name='xendit_account_id',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Xendit xenPlatform sub-account id.',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='companykybverification',
            name='xendit_onboarding_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Link to complete Xendit business verification for the sub-account.',
                max_length=2048,
            ),
        ),
        migrations.AddField(
            model_name='companykybverification',
            name='xendit_rejection_notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='companykybverification',
            name='xendit_status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('pending_xendit', 'Pending Xendit verification'),
                    ('approved', 'Verified'),
                    ('rejected', 'Rejected'),
                ],
                db_index=True,
                default='draft',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='companykybverification',
            name='xendit_submitted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
