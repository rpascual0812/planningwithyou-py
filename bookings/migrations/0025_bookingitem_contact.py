import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0003_alter_contact_account_alter_contactaddress_account_and_more'),
        ('bookings', '0024_booking_pdf_column'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingitem',
            name='contact',
            field=models.ForeignKey(
                blank=True,
                db_column='contact_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bookings',
                to='contacts.contact',
            ),
        ),
    ]
