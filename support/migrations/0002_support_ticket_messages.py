import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_ticket_messages(apps, schema_editor):
    SupportTicket = apps.get_model('support', 'SupportTicket')
    SupportTicketMessage = apps.get_model('support', 'SupportTicketMessage')
    for ticket in SupportTicket.objects.all().iterator():
        body = getattr(ticket, 'message', '') or ''
        if not str(body).strip():
            continue
        SupportTicketMessage.objects.create(
            ticket_id=ticket.pk,
            body=body,
            is_staff=False,
            created_by_id=ticket.created_by_id,
            created_at=ticket.created_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportTicketMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('is_staff', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        db_column='created_by',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='support_ticket_messages_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'ticket',
                    models.ForeignKey(
                        db_column='ticket_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='messages',
                        to='support.supportticket',
                    ),
                ),
            ],
            options={
                'db_table': 'support_ticket_messages',
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.RunPython(migrate_ticket_messages, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='supportticket',
            name='message',
        ),
    ]
