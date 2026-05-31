from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0001_initial'),
        ('emails', '0019_alter_emailtemplate_template_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='GmailIntegration',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('google_email', models.EmailField(blank=True, default='', max_length=255)),
                ('access_token_encrypted', models.TextField(blank=True, default='')),
                ('refresh_token_encrypted', models.TextField(blank=True, default='')),
                ('token_expiry', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'account',
                    models.ForeignKey(
                        db_column='account_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='gmail_integrations',
                        to='users.account',
                    ),
                ),
                (
                    'company',
                    models.ForeignKey(
                        db_column='company_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='gmail_integrations',
                        to='companies.company',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        db_column='created_by',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='gmail_integrations_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'gmail_integrations',
            },
        ),
        migrations.AddConstraint(
            model_name='gmailintegration',
            constraint=models.UniqueConstraint(
                fields=('account', 'company'),
                name='gmail_integrations_one_per_company',
            ),
        ),
    ]
