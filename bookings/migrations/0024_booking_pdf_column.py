from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0023_bookingpdf'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingitem',
            name='pdf',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.DeleteModel(
            name='BookingPdf',
        ),
    ]
