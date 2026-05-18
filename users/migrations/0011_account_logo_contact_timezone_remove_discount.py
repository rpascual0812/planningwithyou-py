import os
import uuid

from django.db import migrations, models


def account_logo_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.png'
    account_id = instance.pk or 'new'
    return f'account_logos/{account_id}/{uuid.uuid4().hex}{ext}'


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_account_country_after_rebuild'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='discount',
        ),
        migrations.RemoveField(
            model_name='account',
            name='price_adjustment',
        ),
        migrations.AddField(
            model_name='account',
            name='logo',
            field=models.FileField(
                blank=True,
                default='',
                upload_to=account_logo_upload_path,
            ),
        ),
        migrations.AddField(
            model_name='account',
            name='contact_person',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='account',
            name='contact_email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
        migrations.AddField(
            model_name='account',
            name='contact_mobile_number',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='account',
            name='timezone',
            field=models.CharField(blank=True, default='', max_length=63),
        ),
    ]
