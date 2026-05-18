from django.db import migrations, models


def set_initial_defaults(apps, schema_editor):
    ContactNumber = apps.get_model('contacts', 'ContactNumber')
    ContactAddress = apps.get_model('contacts', 'ContactAddress')

    for contact_id in (
        ContactNumber.objects.values_list('contact_id', flat=True).distinct()
    ):
        numbers = ContactNumber.objects.filter(contact_id=contact_id).order_by('id')
        if numbers.exists():
            ContactNumber.objects.filter(contact_id=contact_id).update(is_default=False)
            numbers.first().is_default = True
            numbers.first().save(update_fields=['is_default'])

    for contact_id in (
        ContactAddress.objects.values_list('contact_id', flat=True).distinct()
    ):
        addresses = ContactAddress.objects.filter(contact_id=contact_id).order_by('id')
        if addresses.exists():
            ContactAddress.objects.filter(contact_id=contact_id).update(is_default=False)
            addresses.first().is_default = True
            addresses.first().save(update_fields=['is_default'])


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0003_alter_contact_account_alter_contactaddress_account_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='contactnumber',
            name='is_default',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='contactaddress',
            name='is_default',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(set_initial_defaults, migrations.RunPython.noop),
    ]
