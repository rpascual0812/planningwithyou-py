"""Email notifications for quotation lifecycle and payment links."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from companies.contact_email import company_contact_email_address
from companies.models import Company
from emails.mail import create_and_queue_email
from emails.models import EmailTemplate
from emails.tasks import send_email_task
from planningwithyou.file_storage import booking_pdf_api_url, quotation_pdf_available
from planningwithyou.template_placeholders import (
    DEFAULT_NEW_QUOTATION_BODY_HTML,
    DEFAULT_NEW_QUOTATION_SUBJECT,
    DEFAULT_PAYMENT_LINK_BODY_HTML,
    DEFAULT_PAYMENT_LINK_SUBJECT,
    DEFAULT_QUOTATION_STATUS_CONTACT_BODY_HTML,
    DEFAULT_QUOTATION_STATUS_CONTACT_SUBJECT,
    DEFAULT_UPDATED_QUOTATION_BODY_HTML,
    DEFAULT_UPDATED_QUOTATION_SUBJECT,
    EMAIL_TEMPLATE_NEW_QUOTATION,
    EMAIL_TEMPLATE_PAYMENT_LINK,
    EMAIL_TEMPLATE_QUOTATION_STATUS_COMPANY,
    EMAIL_TEMPLATE_QUOTATION_STATUS_CONTACT,
    EMAIL_TEMPLATE_UPDATED_QUOTATION,
    apply_template_placeholders,
    company_template_context,
)

from .models import Quotation, QuotationPaymentLink, QuotationStatus
from .payment_links import public_payment_url

User = get_user_model()

COMPANY_FALLBACK_SUBJECT = 'Quotation {quotation_unique_id} moved to {status_title}'
COMPANY_FALLBACK_BODY = (
    '<p>Hello,</p>'
    '<p>Quotation <strong>{quotation_title}</strong> ({quotation_unique_id}) '
    'has been updated from <strong>{previous_status}</strong> to '
    '<strong>{status_title}</strong>.</p>'
    '<p>Thank you.</p>'
)


def _status_title(status_id: int | None) -> str:
    if not status_id:
        return ''
    title = (
        QuotationStatus.objects.filter(pk=status_id)
        .values_list('title', flat=True)
        .first()
    )
    return (title or '').strip()


def _contact_context(
    quotation: Quotation,
    *,
    previous_status: str = '',
    status_title: str = '',
    payment_link: str = '',
) -> dict[str, str]:
    contact = quotation.contact
    first = (contact.first_name or '').strip() if contact else ''
    last = (contact.last_name or '').strip() if contact else ''
    name = f'{first} {last}'.strip()
    return {
        'name': name,
        'first_name': first,
        'last_name': last,
        'email_address': (contact.email or '').strip() if contact else '',
        'quotation_id': str(quotation.pk),
        'quotation_title': (quotation.title or '').strip(),
        'quotation_unique_id': (quotation.unique_id or '').strip(),
        'status_title': status_title,
        'previous_status': previous_status or '—',
        'payment_link': payment_link,
        **company_template_context(quotation.company),
    }


def _template_for_company(
    *,
    account_id: int,
    company_id: int,
    template_name: str,
) -> EmailTemplate | None:
    return (
        EmailTemplate.objects.filter(
            account_id=account_id,
            company_id=company_id,
            template_type=EmailTemplate.TemplateType.BOOKINGS,
            name=template_name,
            is_active=True,
            deleted_at__isnull=True,
        )
        .order_by('id')
        .first()
    )


def _quotation_pdf_attachments(quotation: Quotation) -> list[str]:
    if not quotation_pdf_available(quotation):
        return []
    return [booking_pdf_api_url(quotation.pk)]


def _send_templated_email(
    *,
    recipient: str,
    template_name: str,
    context: dict[str, str],
    account,
    company: Company,
    actor,
    fallback_subject: str,
    fallback_body: str,
    attachments: list[str] | None = None,
) -> None:
    template = _template_for_company(
        account_id=account.pk,
        company_id=company.pk,
        template_name=template_name,
    )
    subject = fallback_subject
    body = fallback_body
    if template is not None:
        if (template.subject or '').strip():
            subject = template.subject.strip()
        if (template.body or '').strip():
            body = template.body

    log = create_and_queue_email(
        to=[recipient],
        subject=apply_template_placeholders(subject, context),
        body=apply_template_placeholders(body, context),
        email_template=template,
        attachments=attachments or [],
        account=account,
        company=company,
        created_by=actor,
    )
    send_email_task.delay(log.pk)


def _line_companies(quotation: Quotation) -> list[Company]:
    """Distinct supplier companies referenced on quotation lines."""
    company_ids = {
        line.company_id
        for line in quotation.lines.all()
        if line.company_id
    }
    if not company_ids:
        return []
    return list(
        Company.objects.filter(pk__in=company_ids, deleted_at__isnull=True).order_by('id'),
    )


def _quote_template_fallbacks(template_name: str) -> tuple[str, str]:
    if template_name == EMAIL_TEMPLATE_NEW_QUOTATION:
        return DEFAULT_NEW_QUOTATION_SUBJECT, DEFAULT_NEW_QUOTATION_BODY_HTML
    return DEFAULT_UPDATED_QUOTATION_SUBJECT, DEFAULT_UPDATED_QUOTATION_BODY_HTML


def _load_quotation(quotation_id: int) -> Quotation | None:
    return (
        Quotation.objects.select_related('contact', 'company', 'account')
        .prefetch_related('lines')
        .filter(pk=quotation_id)
        .first()
    )


def has_non_status_quotation_changes(changes: dict) -> bool:
    """True when quotation history diff includes fields other than ``status_id``."""
    if not changes:
        return False
    if changes.get('groups') or changes.get('lines'):
        return True
    header = changes.get('quotation') or {}
    return any(field != 'status_id' for field in header)


def send_quotation_quote_emails(
    quotation_id: int,
    *,
    template_name: str,
    actor_id: int | None = None,
) -> None:
    """Email contact and line supplier companies using a New/Updated Quote template."""
    quotation = _load_quotation(quotation_id)
    if quotation is None:
        return

    actor = User.objects.filter(pk=actor_id).first() if actor_id else None
    fallback_subject, fallback_body = _quote_template_fallbacks(template_name)
    context = _contact_context(quotation)
    attachments = _quotation_pdf_attachments(quotation)

    contact_email = (getattr(quotation.contact, 'email', '') or '').strip()
    if contact_email:
        _send_templated_email(
            recipient=contact_email,
            template_name=template_name,
            context=context,
            account=quotation.account,
            company=quotation.company,
            actor=actor,
            fallback_subject=fallback_subject,
            fallback_body=fallback_body,
            attachments=attachments,
        )

    sent_company_emails: set[str] = set()
    for company in _line_companies(quotation):
        recipient = company_contact_email_address(company)
        normalized = recipient.lower()
        if not recipient or normalized in sent_company_emails:
            continue
        sent_company_emails.add(normalized)
        _send_templated_email(
            recipient=recipient,
            template_name=template_name,
            context={
                **_contact_context(quotation),
                **company_template_context(company),
            },
            account=quotation.account,
            company=company,
            actor=actor,
            fallback_subject=fallback_subject,
            fallback_body=fallback_body,
            attachments=attachments,
        )


def send_new_quotation_email(
    quotation_id: int,
    *,
    actor_id: int | None = None,
) -> None:
    send_quotation_quote_emails(
        quotation_id,
        template_name=EMAIL_TEMPLATE_NEW_QUOTATION,
        actor_id=actor_id,
    )


def send_updated_quotation_email(
    quotation_id: int,
    *,
    actor_id: int | None = None,
) -> None:
    send_quotation_quote_emails(
        quotation_id,
        template_name=EMAIL_TEMPLATE_UPDATED_QUOTATION,
        actor_id=actor_id,
    )


def send_quotation_status_emails(
    quotation_id: int,
    *,
    old_status_id: int | None,
    new_status_id: int,
    actor_id: int | None = None,
) -> None:
    if old_status_id == new_status_id:
        return

    quotation = _load_quotation(quotation_id)
    if quotation is None:
        return

    previous_status = _status_title(old_status_id)
    status_title = _status_title(new_status_id)
    actor = User.objects.filter(pk=actor_id).first() if actor_id else None
    status_context = _contact_context(
        quotation,
        previous_status=previous_status,
        status_title=status_title,
    )

    contact_email = (getattr(quotation.contact, 'email', '') or '').strip()
    if contact_email:
        _send_templated_email(
            recipient=contact_email,
            template_name=EMAIL_TEMPLATE_QUOTATION_STATUS_CONTACT,
            context=status_context,
            account=quotation.account,
            company=quotation.company,
            actor=actor,
            fallback_subject=DEFAULT_QUOTATION_STATUS_CONTACT_SUBJECT,
            fallback_body=DEFAULT_QUOTATION_STATUS_CONTACT_BODY_HTML,
            attachments=_quotation_pdf_attachments(quotation),
        )

    sent_company_emails: set[str] = set()
    for company in _line_companies(quotation):
        recipient = company_contact_email_address(company)
        normalized = recipient.lower()
        if not recipient or normalized in sent_company_emails:
            continue
        sent_company_emails.add(normalized)
        context = {
            **status_context,
            **company_template_context(company),
        }
        _send_templated_email(
            recipient=recipient,
            template_name=EMAIL_TEMPLATE_QUOTATION_STATUS_COMPANY,
            context=context,
            account=quotation.account,
            company=company,
            actor=actor,
            fallback_subject=COMPANY_FALLBACK_SUBJECT,
            fallback_body=COMPANY_FALLBACK_BODY,
        )


def send_payment_link_email(
    quotation_id: int,
    *,
    payment_link_id: int | None = None,
    actor_id: int | None = None,
) -> None:
    quotation = _load_quotation(quotation_id)
    if quotation is None:
        return

    contact_email = (getattr(quotation.contact, 'email', '') or '').strip()
    if not contact_email:
        return

    link_qs = QuotationPaymentLink.objects.filter(quotation_id=quotation_id)
    if payment_link_id is not None:
        link = link_qs.filter(pk=payment_link_id).first()
    else:
        link = (
            link_qs.filter(status=QuotationPaymentLink.Status.PENDING)
            .order_by('-created_at')
            .first()
        )
    if link is None:
        return

    actor = User.objects.filter(pk=actor_id).first() if actor_id else None
    payment_url = public_payment_url(link.public_token)
    _send_templated_email(
        recipient=contact_email,
        template_name=EMAIL_TEMPLATE_PAYMENT_LINK,
        context=_contact_context(quotation, payment_link=payment_url),
        account=quotation.account,
        company=quotation.company,
        actor=actor,
        fallback_subject=DEFAULT_PAYMENT_LINK_SUBJECT,
        fallback_body=DEFAULT_PAYMENT_LINK_BODY_HTML,
    )


def schedule_new_quotation_email(
    quotation_id: int,
    *,
    actor_id: int | None = None,
) -> None:
    from django.db import transaction

    transaction.on_commit(
        lambda: send_new_quotation_email(quotation_id, actor_id=actor_id),
    )


def schedule_updated_quotation_email(
    quotation_id: int,
    *,
    actor_id: int | None = None,
) -> None:
    from django.db import transaction

    transaction.on_commit(
        lambda: send_updated_quotation_email(quotation_id, actor_id=actor_id),
    )


def schedule_quotation_status_emails(
    quotation_id: int,
    *,
    old_status_id: int | None,
    new_status_id: int,
    actor_id: int | None = None,
) -> None:
    from django.db import transaction

    transaction.on_commit(
        lambda: send_quotation_status_emails(
            quotation_id,
            old_status_id=old_status_id,
            new_status_id=new_status_id,
            actor_id=actor_id,
        ),
    )


def schedule_payment_link_email(
    quotation_id: int,
    *,
    payment_link_id: int | None = None,
    actor_id: int | None = None,
) -> None:
    from django.db import transaction

    transaction.on_commit(
        lambda: send_payment_link_email(
            quotation_id,
            payment_link_id=payment_link_id,
            actor_id=actor_id,
        ),
    )
