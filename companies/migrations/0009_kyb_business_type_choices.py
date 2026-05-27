from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0008_kyb_paymongo_onboarding'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companykybverification',
            name='business_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('individual', 'Individual'),
                    ('sole_proprietor', 'Sole proprietorship'),
                    ('partnership', 'Partnership'),
                    ('corporation', 'Corporation'),
                ],
                default='',
                max_length=32,
            ),
        ),
    ]
