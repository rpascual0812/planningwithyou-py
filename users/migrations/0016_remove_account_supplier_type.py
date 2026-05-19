from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0015_user_company'),
        ('companies', '0002_company_supplier_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='supplier_type',
        ),
    ]
