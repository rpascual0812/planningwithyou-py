import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0022_booking_unique_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookingPdf',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_path', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('booking', models.OneToOneField(
                    db_column='booking_id',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pdf_file',
                    to='bookings.bookingitem',
                )),
            ],
            options={
                'db_table': 'bookings_pdf',
            },
        ),
    ]
