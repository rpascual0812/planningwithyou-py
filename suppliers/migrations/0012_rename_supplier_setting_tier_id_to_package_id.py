from django.db import migrations


class Migration(migrations.Migration):
    """
    0011 RenameField(tier -> package) did not rename the physical column when the
    original FK used db_column='tier_id'. The ORM expects package_id.
    """

    dependencies = [
        ('suppliers', '0011_rename_tier_to_package'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = 'supplier_setting_packages'
                          AND column_name = 'tier_id'
                    ) THEN
                        ALTER TABLE supplier_setting_packages
                            RENAME COLUMN tier_id TO package_id;
                    END IF;
                END $$;
            """,
            reverse_sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = 'supplier_setting_packages'
                          AND column_name = 'package_id'
                    ) THEN
                        ALTER TABLE supplier_setting_packages
                            RENAME COLUMN package_id TO tier_id;
                    END IF;
                END $$;
            """,
        ),
    ]
