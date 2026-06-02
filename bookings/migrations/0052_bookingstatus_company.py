import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0010_company_contact_email'),
        ('bookings', '0051_seed_default_company_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingstatus',
            name='company',
            field=models.ForeignKey(
                blank=True,
                db_column='company_id',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='booking_statuses',
                to='companies.company',
            ),
        ),
    ]
