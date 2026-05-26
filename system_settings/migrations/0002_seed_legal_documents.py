from django.db import migrations

LEGAL_DOCUMENT_NAMES = (
    'privacy_policy',
    'terms_condition',
    'terms_use',
)


def seed_legal_documents(apps, schema_editor):
    SystemSetting = apps.get_model('system_settings', 'SystemSetting')
    for name in LEGAL_DOCUMENT_NAMES:
        SystemSetting.objects.get_or_create(name=name, defaults={'value': ''})


class Migration(migrations.Migration):

    dependencies = [
        ('system_settings', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_legal_documents, migrations.RunPython.noop),
    ]
