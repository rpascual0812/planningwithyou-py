from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0011_ensure_main_company_per_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='business_legal_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
