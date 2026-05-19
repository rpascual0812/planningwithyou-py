from django.conf import settings
from django.db import migrations, models


def _package_columns(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = CURRENT_SCHEMA()
              AND table_name = 'packages'
              AND column_name IN ('created_by', 'created_by_id')
            """,
        )
        return {row[0] for row in cursor.fetchall()}


def ensure_created_by_column(apps, schema_editor):
    cols = _package_columns(schema_editor)
    if 'created_by' in cols:
        return
    if 'created_by_id' in cols:
        schema_editor.execute(
            'ALTER TABLE packages RENAME COLUMN created_by_id TO created_by',
        )


def reverse_ensure_created_by_column(apps, schema_editor):
    cols = _package_columns(schema_editor)
    if 'created_by_id' in cols or 'created_by' not in cols:
        return
    schema_editor.execute(
        'ALTER TABLE packages RENAME COLUMN created_by TO created_by_id',
    )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('packages', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    ensure_created_by_column,
                    reverse_ensure_created_by_column,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='package',
                    name='created_by',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='created_by',
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name='packages_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
