import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0010_company_contact_email'),
        ('bookings', '0053_seed_company_booking_statuses'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bookingstatus',
            name='company',
            field=models.ForeignKey(
                db_column='company_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='booking_statuses',
                to='companies.company',
            ),
        ),
    ]
