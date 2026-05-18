import logging
import re

from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
from mailjet_rest import Client

from users.models import Account

from .attachments import build_mailjet_attachments
from .models import EmailLog

logger = logging.getLogger(__name__)


def _html_to_plaintext(html: str) -> str:
    """Best-effort plain text for the mail transport (not stored on EmailLog)."""
    if not html or not html.strip():
        return ''
    text = strip_tags(html)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\u00a0', ' ', text)
    return text.strip()


def body_has_content(html: str) -> bool:
    """True when HTML body has visible text (not just empty TinyMCE markup)."""
    return bool(_html_to_plaintext(html))


def _prepare_message_parts(body: str) -> tuple[str, str]:
    """
    Return (HTMLPart, TextPart) for Mailjet.

    Mailjet rejects messages when HTMLPart, TextPart, and TemplateID are all
    missing/empty. Ensure at least one non-empty part is always sent.
    """
    html = (body or '').strip()
    text = _html_to_plaintext(html)
    if text:
        if not html:
            html = f'<p>{text}</p>'
        return html, text
    if html:
        return html, ' '
    return '<p> </p>', ' '


def _get_client():
    return Client(
        auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY),
        version='v3.1',
    )


def _raise_on_mailjet_errors(result) -> None:
    """Mailjet may return HTTP 200 with per-message errors."""
    try:
        payload = result.json()
    except Exception:
        return
    messages = payload.get('Messages') or []
    errors = []
    for msg in messages:
        if msg.get('Status') == 'error':
            parts = msg.get('Errors') or []
            errors.extend(
                err.get('ErrorMessage', str(err)) for err in parts if err
            )
    if errors:
        raise RuntimeError('; '.join(errors))


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
    }
    html_part, text_part = _prepare_message_parts(log.body)
    message['HTMLPart'] = html_part
    message['TextPart'] = text_part
    if cc_list:
        message['Cc'] = cc_list
    if bcc_list:
        message['Bcc'] = bcc_list
    if log.reply_to:
        message['ReplyTo'] = {'Email': log.reply_to}

    attachment_items = [item for item in (log.attachments or []) if item not in (None, '')]
    if attachment_items:
        mailjet_attachments, attachment_errors = build_mailjet_attachments(
            attachment_items,
            account_id=log.account_id,
        )
        if len(mailjet_attachments) != len(attachment_items):
            failed = '; '.join(attachment_errors) or 'unknown error'
            raise RuntimeError(
                f'Could not load {len(attachment_items) - len(mailjet_attachments)} '
                f'of {len(attachment_items)} attachment(s): {failed}',
            )
        message['Attachments'] = mailjet_attachments
        logger.info(
            'Email log %s: attaching %s file(s) to Mailjet message',
            log.pk,
            len(mailjet_attachments),
        )

    try:
        result = _get_client().send.create(data={'Messages': [message]})
        logger.info(
            'Mailjet send status=%s to=%s (log=%s, attachments=%s)',
            result.status_code,
            log.to,
            log.pk,
            len(message.get('Attachments', [])),
        )
        if result.status_code >= 400:
            raise RuntimeError(
                f'Mailjet returned {result.status_code}: {result.json()}'
            )
        _raise_on_mailjet_errors(result)
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
    reply_to: str = '',
    attachments: list | None = None,
    account=None,
) -> EmailLog:
    """Create an EmailLog record and return it (caller dispatches the task)."""
    kwargs = dict(
        to=to,
        cc=cc or [],
        bcc=bcc or [],
        email_from=email_from or settings.MAILJET_SEND_FROM,
        reply_to=reply_to or '',
        subject=subject,
        body=body,
        attachments=attachments or [],
        status=EmailLog.Status.QUEUED,
        account=account if account is not None else Account.objects.get(pk=1),
    )
    return EmailLog.objects.create(**kwargs)
