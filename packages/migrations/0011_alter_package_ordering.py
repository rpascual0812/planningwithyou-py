from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('packages', '0010_package_one_active_per_scope'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='package',
            options={'ordering': ['tier_id', 'id']},
        ),
    ]
