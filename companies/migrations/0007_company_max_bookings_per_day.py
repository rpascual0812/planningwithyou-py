from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0006_remove_companykybverification_selfie_verification_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='max_bookings_per_day',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
