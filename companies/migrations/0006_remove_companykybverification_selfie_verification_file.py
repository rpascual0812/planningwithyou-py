from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0005_company_kyb_verified'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='companykybverification',
            name='selfie_verification_file',
        ),
    ]
