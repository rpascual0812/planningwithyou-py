from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_company_supplier_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='contact_person',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='company',
            name='phone_number',
            field=models.CharField(blank=True, default='', max_length=63),
        ),
        migrations.AddField(
            model_name='company',
            name='mobile_number',
            field=models.CharField(blank=True, default='', max_length=63),
        ),
        migrations.AddField(
            model_name='company',
            name='address',
            field=models.TextField(blank=True, default=''),
        ),
    ]
