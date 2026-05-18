from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bookings', '0025_bookingitem_contact'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingitem',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                db_column='created_by',
                null=True,
                on_delete=models.SET_NULL,
                related_name='bookings_created',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
