"""Email notifications for company KYB / PayMongo child account outcomes."""

from __future__ import annotations

import logging

from emails.mail import create_and_queue_email
from emails.models import EmailTemplate
from emails.tasks import send_email_task
from planningwithyou.template_placeholders import (
    apply_template_placeholders,
    company_template_context,
)

from .contact_email import company_contact_email_address
from .models import Company

logger = logging.getLogger(__name__)

KYB_VERIFIED_TEMPLATE_NAME = 'kyb_verified'

DEFAULT_KYB_VERIFIED_SUBJECT = 'Your business verification is approved – {company_name}'
DEFAULT_KYB_VERIFIED_BODY = (
    '<h3>Hello,</h3>'
    '<p>Your Know Your Business (KYB) verification for <strong>{company_name}</strong> '
    'has been approved.</p>'
    '<p>You can now accept live payments through Planning With You.</p>'
    '<p>If you have questions, reply to this email.</p>'
    '<p>Thank you,<br>{company_name}</p>'
)


def _template_for_company(company: Company) -> EmailTemplate | None:
    return (
        EmailTemplate.objects.filter(
            account_id=company.account_id,
            company_id=company.pk,
            template_type=EmailTemplate.TemplateType.USERS,
            name=KYB_VERIFIED_TEMPLATE_NAME,
            is_active=True,
            deleted_at__isnull=True,
        )
        .order_by('id')
        .first()
    )


def send_company_kyb_approved_email(company_id: int) -> bool:
    """
    Notify ``companies.contact_email`` (or first company user) that KYB is approved.

    Returns True when an email was queued.
    """
    company = (
        Company.objects.filter(pk=company_id, deleted_at__isnull=True)
        .select_related('account')
        .first()
    )
    if company is None:
        logger.warning('KYB approval email skipped: company %s not found', company_id)
        return False

    recipient = company_contact_email_address(company)
    if not recipient:
        logger.warning(
            'KYB approval email skipped: no contact email for company %s',
            company_id,
        )
        return False

    context = company_template_context(company)
    template = _template_for_company(company)
    subject = DEFAULT_KYB_VERIFIED_SUBJECT
    body = DEFAULT_KYB_VERIFIED_BODY
    if template is not None:
        if (template.subject or '').strip():
            subject = template.subject.strip()
        if (template.body or '').strip():
            body = template.body

    log = create_and_queue_email(
        to=[recipient],
        subject=apply_template_placeholders(subject, context),
        body=apply_template_placeholders(body, context),
        account=company.account,
        company=company,
    )
    send_email_task.delay(log.pk)
    logger.info(
        'Queued KYB approval email for company %s to %s',
        company_id,
        recipient,
    )
    return True
