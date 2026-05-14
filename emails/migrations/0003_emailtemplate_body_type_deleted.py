# Generated manually for email_templates schema change

from django.db import migrations, models


def merge_template_bodies(apps, schema_editor):
    EmailTemplate = apps.get_model('emails', 'EmailTemplate')
    for t in EmailTemplate.objects.all():
        chunks = []
        if getattr(t, 'subject', ''):
            chunks.append(f'Subject: {t.subject}')
        if getattr(t, 'body_html', ''):
            chunks.append(str(t.body_html))
        if getattr(t, 'body_text', ''):
            chunks.append(str(t.body_text))
        t.body = '\n\n'.join(c for c in chunks if c.strip())
        t.save(update_fields=['body'])


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0002_emailtemplate'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailtemplate',
            name='body',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='emailtemplate',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(merge_template_bodies, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='emailtemplate',
            name='subject',
        ),
        migrations.RemoveField(
            model_name='emailtemplate',
            name='body_html',
        ),
        migrations.RemoveField(
            model_name='emailtemplate',
            name='body_text',
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE email_templates RENAME COLUMN template_type TO "type";',
                    reverse_sql='ALTER TABLE email_templates RENAME COLUMN "type" TO template_type;',
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='emailtemplate',
                    name='template_type',
                    field=models.CharField(
                        choices=[('users', 'Users')],
                        db_column='type',
                        db_index=True,
                        max_length=32,
                    ),
                ),
            ],
        ),
    ]
