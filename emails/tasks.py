from celery import shared_task

from .mail import send_email


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, email_log_id: int):
    try:
        send_email(email_log_id)
    except Exception as exc:
        raise self.retry(exc=exc)
