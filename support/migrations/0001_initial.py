import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('open', 'Open'),
                            ('in_progress', 'In progress'),
                            ('resolved', 'Resolved'),
                            ('closed', 'Closed'),
                        ],
                        default='open',
                        max_length=32,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        db_column='created_by',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='support_tickets_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'support_tickets',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='SupportTicketRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('read_at', models.DateTimeField(auto_now_add=True)),
                (
                    'ticket',
                    models.ForeignKey(
                        db_column='ticket_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='reads',
                        to='support.supportticket',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        db_column='user_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='support_ticket_reads',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'support_ticket_reads',
            },
        ),
        migrations.AddConstraint(
            model_name='supportticketread',
            constraint=models.UniqueConstraint(
                fields=('ticket', 'user'),
                name='support_ticket_reads_ticket_user_uniq',
            ),
        ),
    ]
