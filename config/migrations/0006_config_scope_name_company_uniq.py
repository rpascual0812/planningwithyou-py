from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0010_company_contact_email'),
        ('config', '0005_errorlog_resolved'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='config',
            name='config_account_scope_name_uniq',
        ),
        migrations.AddConstraint(
            model_name='config',
            constraint=models.UniqueConstraint(
                fields=('account', 'scope', 'name', 'company'),
                name='config_account_scope_name_company_uniq',
            ),
        ),
    ]
