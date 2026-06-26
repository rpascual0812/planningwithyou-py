from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from emails.mail import create_and_queue_email
from emails.models import EmailTemplate
from emails.tasks import send_email_task
from planningwithyou.template_placeholders import (
    EMAIL_TEMPLATE_CALENDAR_EVENT_REMINDER,
    apply_template_placeholders,
    company_template_context,
    user_template_context,
)

from .models import AppointmentReminder, Calendar, ScheduledAppointmentReminder
from .notifications import _event_context, _template_for_event


def _offset_timedelta(reminder: AppointmentReminder) -> timedelta:
    amount = reminder.frequency
    unit = (reminder.unit or '').rstrip('s')
    if unit == 'minute':
        return timedelta(minutes=amount)
    if unit == 'hour':
        return timedelta(hours=amount)
    if unit == 'day':
        return timedelta(days=amount)
    if unit == 'week':
        return timedelta(weeks=amount)
    return timedelta(hours=amount)


def compute_reminder_send_at(event: Calendar, reminder: AppointmentReminder):
    anchor = event.end if reminder.calendar == AppointmentReminder.CalendarAnchor.END else event.start
    return anchor - _offset_timedelta(reminder)


def _matching_reminders(event: Calendar) -> list[AppointmentReminder]:
    reminders = (
        AppointmentReminder.objects.filter(
            account_id=event.account_id,
            company_id=event.company_id,
            is_active=True,
            reminder_type=AppointmentReminder.ReminderType.EMAIL,
        )
        .prefetch_related('calendar_statuses')
    )
    matched: list[AppointmentReminder] = []
    for reminder in reminders:
        status_ids = {status.pk for status in reminder.calendar_statuses.all()}
        if status_ids and event.status_id not in status_ids:
            continue
        matched.append(reminder)
    return matched


def _recipient_targets(event: Calendar) -> list[tuple[str, str, str]]:
    """Return (role, email, display_name) tuples for contact and author."""
    targets: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    contact = event.contact
    contact_email = (getattr(contact, 'email', '') or '').strip()
    if contact_email:
        first = (getattr(contact, 'first_name', '') or '').strip()
        last = (getattr(contact, 'last_name', '') or '').strip()
        name = f'{first} {last}'.strip()
        key = contact_email.lower()
        if key not in seen:
            seen.add(key)
            targets.append(
                (ScheduledAppointmentReminder.RecipientRole.CONTACT, contact_email, name),
            )

    author = event.created_by
    author_email = (getattr(author, 'email', '') or '').strip()
    if author_email:
        ctx = user_template_context(author)
        key = author_email.lower()
        if key not in seen:
            seen.add(key)
            targets.append(
                (ScheduledAppointmentReminder.RecipientRole.AUTHOR, author_email, ctx['name']),
            )
    return targets


def _create_scheduled_reminders_for_event(event_id: int) -> None:
    event = (
        Calendar.objects.select_related(
            'contact',
            'created_by',
            'company',
            'status',
        )
        .filter(pk=event_id, deleted_at__isnull=True)
        .first()
    )
    if event is None:
        return

    now = timezone.now()
    targets = _recipient_targets(event)
    if not targets:
        return

    for reminder in _matching_reminders(event):
        send_at = compute_reminder_send_at(event, reminder)
        if send_at <= now:
            continue
        for role, email, name in targets:
            ScheduledAppointmentReminder.objects.create(
                account_id=event.account_id,
                company_id=event.company_id,
                calendar_event=event,
                appointment_reminder=reminder,
                recipient_role=role,
                recipient_email=email,
                recipient_name=name,
                send_at=send_at,
                status=ScheduledAppointmentReminder.Status.PENDING,
            )


def _clear_pending_scheduled(event_id: int) -> None:
    ScheduledAppointmentReminder.objects.filter(
        calendar_event_id=event_id,
        status=ScheduledAppointmentReminder.Status.PENDING,
    ).delete()


def schedule_appointment_reminders_for_event(event: Calendar) -> None:
    transaction.on_commit(lambda: _create_scheduled_reminders_for_event(event.pk))


def reschedule_appointment_reminders_for_event(event: Calendar) -> None:
    def _run() -> None:
        _clear_pending_scheduled(event.pk)
        _create_scheduled_reminders_for_event(event.pk)

    transaction.on_commit(_run)


def cancel_appointment_reminders_for_event(event: Calendar) -> None:
    ScheduledAppointmentReminder.objects.filter(
        calendar_event_id=event.pk,
        status=ScheduledAppointmentReminder.Status.PENDING,
        deleted_at__isnull=True,
    ).update(
        status=ScheduledAppointmentReminder.Status.CANCELLED,
        updated_at=timezone.now(),
    )


def _recipient_context_for_scheduled(scheduled: ScheduledAppointmentReminder) -> dict[str, str]:
    event = scheduled.calendar_event
    if scheduled.recipient_role == ScheduledAppointmentReminder.RecipientRole.AUTHOR:
        base = user_template_context(event.created_by)
    else:
        contact = event.contact
        first = (getattr(contact, 'first_name', '') or '').strip()
        last = (getattr(contact, 'last_name', '') or '').strip()
        base = {
            'name': f'{first} {last}'.strip(),
            'first_name': first,
            'last_name': last,
            'email_address': scheduled.recipient_email,
            'mobile_number': '',
        }
    local_start = timezone.localtime(event.start)
    return {
        **base,
        **company_template_context(event.company),
        **_event_context(event),
        'event_date': local_start.strftime('%b %d, %Y'),
        'event_time': local_start.strftime('%I:%M %p'),
    }


def send_scheduled_appointment_reminder(scheduled_id: int) -> None:
    scheduled = (
        ScheduledAppointmentReminder.objects.select_related(
            'calendar_event',
            'calendar_event__contact',
            'calendar_event__created_by',
            'calendar_event__company',
            'appointment_reminder',
        )
        .filter(pk=scheduled_id)
        .first()
    )
    if scheduled is None:
        return
    if scheduled.deleted_at is not None:
        return
    if scheduled.status != ScheduledAppointmentReminder.Status.PENDING:
        return

    event = scheduled.calendar_event
    if event.deleted_at is not None:
        scheduled.status = ScheduledAppointmentReminder.Status.CANCELLED
        scheduled.save(update_fields=['status', 'updated_at'])
        return

    context = _recipient_context_for_scheduled(scheduled)
    template = _template_for_event(event, EMAIL_TEMPLATE_CALENDAR_EVENT_REMINDER)
    subject = '{company_name} - Appointment reminder'
    body = (
        '<p>Hi {first_name} {last_name},</p>'
        '<p>This is a reminder about your upcoming appointment:</p>'
        '<p>Title: {event_title}</p>'
        '<p>Date: {event_date}</p>'
        '<p>Time: {event_time}</p>'
        '<p>Location: {event_location}</p>'
        '<p>Thank you.</p>'
    )
    if template is not None:
        if (template.subject or '').strip():
            subject = template.subject.strip()
        if (template.body or '').strip():
            body = template.body

    try:
        log = create_and_queue_email(
            to=[scheduled.recipient_email],
            subject=apply_template_placeholders(subject, context),
            body=apply_template_placeholders(body, context),
            email_template=template,
            account=event.account,
            company=event.company,
            created_by=event.created_by,
        )
        send_email_task.delay(log.pk)
        scheduled.email_log = log
        scheduled.status = ScheduledAppointmentReminder.Status.SENT
        scheduled.sent_at = timezone.now()
        scheduled.error = ''
        scheduled.save(
            update_fields=['email_log', 'status', 'sent_at', 'error', 'updated_at'],
        )
    except Exception as exc:
        scheduled.status = ScheduledAppointmentReminder.Status.FAILED
        scheduled.error = str(exc)
        scheduled.save(update_fields=['status', 'error', 'updated_at'])
        raise


def dispatch_due_appointment_reminders() -> int:
    """Send all pending scheduled reminders whose send_at is in the past."""
    now = timezone.now()
    due_ids = list(
        ScheduledAppointmentReminder.objects.filter(
            status=ScheduledAppointmentReminder.Status.PENDING,
            deleted_at__isnull=True,
            send_at__lte=now,
        )
        .order_by('send_at', 'id')
        .values_list('pk', flat=True)[:200],
    )
    for scheduled_id in due_ids:
        try:
            send_scheduled_appointment_reminder(scheduled_id)
        except Exception:
            continue
    return len(due_ids)
