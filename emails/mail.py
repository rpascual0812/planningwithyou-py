import logging

from django.conf import settings
from django.utils import timezone
from mailjet_rest import Client

from .models import EmailLog

logger = logging.getLogger(__name__)


def _get_client():
    return Client(
        auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY),
        version='v3.1',
    )


def send_email(email_log_id: int):
    """Send (or re-send) an email identified by its EmailLog pk."""
    log = EmailLog.objects.get(pk=email_log_id)
    log.attempts += 1

    to_list = [{'Email': addr} for addr in log.to]
    cc_list = [{'Email': addr} for addr in log.cc] if log.cc else []
    bcc_list = [{'Email': addr} for addr in log.bcc] if log.bcc else []

    message: dict = {
        'From': {
            'Email': log.email_from,
            'Name': settings.MAILJET_SENDER_NAME,
        },
        'To': to_list,
        'Subject': log.subject,
        'HTMLPart': log.body_html,
        'TextPart': log.body_text,
    }
    if cc_list:
        message['Cc'] = cc_list
    if bcc_list:
        message['Bcc'] = bcc_list

    try:
        result = _get_client().send.create(data={'Messages': [message]})
        logger.info(
            'Mailjet send status=%s to=%s (log=%s)',
            result.status_code,
            log.to,
            log.pk,
        )
        if result.status_code >= 400:
            raise RuntimeError(
                f'Mailjet returned {result.status_code}: {result.json()}'
            )
        log.status = EmailLog.Status.SENT
        log.error = ''
        log.sent_at = timezone.now()
        log.save(update_fields=['status', 'error', 'sent_at', 'attempts'])
    except Exception as exc:
        log.status = EmailLog.Status.FAILED
        log.error = str(exc)
        log.save(update_fields=['status', 'error', 'attempts'])
        raise


def create_and_queue_email(
    *,
    to: list[str],
    subject: str,
    body_html: str,
    body_text: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    email_from: str = '',
    attachments: list[str] | None = None,
    account=None,
) -> EmailLog:
    """Create an EmailLog record and return it (caller dispatches the task)."""
    kwargs = dict(
        to=to,
        cc=cc or [],
        bcc=bcc or [],
        email_from=email_from or settings.MAILJET_SEND_FROM,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        attachments=attachments or [],
        status=EmailLog.Status.QUEUED,
    )
    if account is not None:
        kwargs['account'] = account
    return EmailLog.objects.create(**kwargs)
