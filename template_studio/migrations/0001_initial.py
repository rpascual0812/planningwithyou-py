from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('companies', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InvitationTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=120)),
                ('category', models.CharField(default='wedding', max_length=50)),
                ('description', models.TextField(blank=True, default='')),
                ('document', models.JSONField(default=dict)),
                ('is_published', models.BooleanField(default=False)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('is_marketplace', models.BooleanField(default=False, help_text='System catalog template visible to all tenants.')),
                ('marketplace_preview_url', models.URLField(blank=True, default='')),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(blank=True, db_column='account_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='invitation_templates', to='users.account')),
                ('company', models.ForeignKey(blank=True, db_column='company_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='invitation_templates', to='companies.company')),
                ('created_by', models.ForeignKey(blank=True, db_column='created_by_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_invitation_templates', to='users.user')),
            ],
            options={
                'db_table': 'invitation_templates',
                'ordering': ['-updated_at'],
            },
        ),
    ]
