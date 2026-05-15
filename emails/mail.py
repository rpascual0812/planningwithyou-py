import logging
import re

from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
from mailjet_rest import Client

from users.models import Account

from .models import EmailLog

logger = logging.getLogger(__name__)


def _html_to_plaintext(html: str) -> str:
    """Best-effort plain text for the mail transport (not stored on EmailLog)."""
    if not html or not html.strip():
        return ''
    text = strip_tags(html)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


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
        'HTMLPart': log.body,
        'TextPart': _html_to_plaintext(log.body),
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
    body: str,
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
        body=body,
        attachments=attachments or [],
        status=EmailLog.Status.QUEUED,
        account=account if account is not None else Account.objects.get(pk=1),
    )
    return EmailLog.objects.create(**kwargs)
