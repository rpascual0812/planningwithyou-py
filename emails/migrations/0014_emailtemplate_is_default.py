from django.db import migrations, models


def set_existing_templates_default(apps, schema_editor):
    EmailTemplate = apps.get_model('emails', 'EmailTemplate')
    EmailTemplate.objects.all().update(is_default=True)


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0013_emaillog_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailtemplate',
            name='is_default',
            field=models.BooleanField(
                default=False,
                help_text='System-seeded templates; not deletable from the app.',
            ),
        ),
        migrations.RunPython(set_existing_templates_default, migrations.RunPython.noop),
    ]
