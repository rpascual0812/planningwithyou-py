from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0060_quotationline_supplier_type'),
        ('documents', '0006_document_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='quotation',
            field=models.ForeignKey(
                blank=True,
                db_column='quotation_id',
                help_text='When set, document is visible only on that quotation (not File Manager).',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='documents',
                to='bookings.quotation',
            ),
        ),
    ]
