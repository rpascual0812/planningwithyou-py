from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plan', models.CharField(max_length=64)),
                ('name', models.CharField(max_length=255)),
                ('subtitle', models.TextField(blank=True, default='')),
                ('features', models.JSONField(blank=True, default=list)),
                ('billing_cycle', models.CharField(choices=[('monthly', 'Monthly'), ('yearly', 'Yearly')], max_length=20)),
                ('base_price', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('price_per_user', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('default_users', models.PositiveIntegerField(default=1)),
                ('has_team_stepper', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'subscriptions',
                'ordering': ['sort_order', 'plan'],
            },
        ),
        migrations.AddConstraint(
            model_name='subscription',
            constraint=models.UniqueConstraint(
                fields=('plan', 'billing_cycle'),
                name='subscriptions_plan_billing_cycle_uniq',
            ),
        ),
    ]
