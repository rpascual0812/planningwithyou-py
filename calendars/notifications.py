from __future__ import annotations

from django.utils import timezone

from emails.mail import create_and_queue_email
from emails.models import EmailTemplate
from emails.tasks import send_email_task
from planningwithyou.template_placeholders import (
    apply_template_placeholders,
    company_template_context,
)


def _recipient_context(event) -> dict[str, str]:
    contact = event.contact
    if contact is None:
        return {
            'name': '',
            'first_name': '',
            'last_name': '',
            'email_address': '',
            'mobile_number': '',
        }
    first = (contact.first_name or '').strip()
    last = (contact.last_name or '').strip()
    return {
        'name': f'{first} {last}'.strip(),
        'first_name': first,
        'last_name': last,
        'email_address': (contact.email or '').strip(),
        'mobile_number': '',
    }


def _event_context(event) -> dict[str, str]:
    return {
        'event_title': (event.title or '').strip(),
        'event_start': timezone.localtime(event.start).strftime('%b %d, %Y %I:%M %p'),
        'event_end': timezone.localtime(event.end).strftime('%b %d, %Y %I:%M %p'),
        'event_location': (event.location or '').strip(),
    }


def _template_for_event(event, template_name: str):
    return (
        EmailTemplate.objects.filter(
            account_id=event.account_id,
            company_id=event.company_id,
            template_type=EmailTemplate.TemplateType.CALENDAR,
            name=template_name,
            is_active=True,
            deleted_at__isnull=True,
        )
        .order_by('id')
        .first()
    )


def send_calendar_event_email(event, *, template_name: str, fallback_subject: str) -> None:
    contact = event.contact
    recipient = (getattr(contact, 'email', '') or '').strip()
    if not recipient:
        return

    cc_list: list[str] = []
    creator_email = (getattr(event.created_by, 'email', '') or '').strip()
    if creator_email and creator_email.lower() != recipient.lower():
        cc_list.append(creator_email)

    context = {
        **_recipient_context(event),
        **company_template_context(event.company),
        **_event_context(event),
    }
    template = _template_for_event(event, template_name)
    subject = fallback_subject
    body = (
        '<p>Event details:</p>'
        '<p>Title: {event_title}</p>'
        '<p>Start: {event_start}</p>'
        '<p>End: {event_end}</p>'
        '<p>Location: {event_location}</p>'
    )
    if template is not None:
        if (template.subject or '').strip():
            subject = template.subject.strip()
        if (template.body or '').strip():
            body = template.body

    log = create_and_queue_email(
        to=[recipient],
        cc=cc_list,
        subject=apply_template_placeholders(subject, context),
        body=apply_template_placeholders(body, context),
        email_template=template,
        account=event.account,
        company=event.company,
        created_by=event.created_by,
    )
    send_email_task.delay(log.pk)
