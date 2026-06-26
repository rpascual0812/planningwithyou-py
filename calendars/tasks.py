from celery import shared_task

from .reminders import dispatch_due_appointment_reminders


@shared_task
def dispatch_due_appointment_reminders_task() -> int:
    return dispatch_due_appointment_reminders()
