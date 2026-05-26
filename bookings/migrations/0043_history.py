import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0001_initial'),
        ('bookings', '0042_bookingpayment_payout_sent_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='History',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entity_type', models.CharField(choices=[('booking', 'Booking'), ('booking_line', 'Booking line'), ('booking_group', 'Booking group')], max_length=20)),
                ('entity_id', models.PositiveIntegerField(blank=True, null=True)),
                ('action', models.CharField(choices=[('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('replace', 'Replace')], max_length=20)),
                ('changes', models.JSONField(default=dict)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(db_column='account_id', on_delete=django.db.models.deletion.CASCADE, related_name='+', to='users.account')),
                ('actor', models.ForeignKey(blank=True, db_column='actor_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='booking_history_entries', to=settings.AUTH_USER_MODEL)),
                ('booking', models.ForeignKey(blank=True, db_column='booking_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='history_entries', to='bookings.bookingitem')),
            ],
            options={
                'db_table': 'history',
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['booking', '-created_at'], name='history_booking_created_idx'), models.Index(fields=['account', '-created_at'], name='history_account_created_idx')],
            },
        ),
    ]
