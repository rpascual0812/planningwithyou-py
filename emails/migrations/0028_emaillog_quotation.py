import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0060_quotationline_supplier_type'),
        ('emails', '0027_gmail_integration_created_at_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='emaillog',
            name='quotation',
            field=models.ForeignKey(
                blank=True,
                db_column='quotation_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='email_logs',
                to='bookings.quotation',
            ),
        ),
    ]
