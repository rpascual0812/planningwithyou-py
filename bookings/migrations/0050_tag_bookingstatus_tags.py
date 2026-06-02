import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0001_initial'),
        ('bookings', '0049_merge_20260528_0805'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tag', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('account', models.ForeignKey(db_column='account_id', on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='users.account')),
                ('company', models.ForeignKey(blank=True, db_column='company_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='companies.company')),
                ('created_by', models.ForeignKey(blank=True, db_column='created_by', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tags_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'tags',
                'ordering': ['tag', 'id'],
            },
        ),
        migrations.AddField(
            model_name='bookingstatus',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='booking_statuses', to='bookings.tag'),
        ),
    ]
