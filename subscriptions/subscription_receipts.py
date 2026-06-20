from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from companies.models import Company
from emails.mail import create_and_queue_email
from emails.tasks import send_email_task

from .models import SubscriptionPayment, SubscriptionReceipt
from .subscription_billing_notifications import payment_qualifies_for_receipt


def _currency(amount: Decimal) -> str:
    return f'PHP {amount:.2f}'


def _subscription_receipt_attachment(receipt: SubscriptionReceipt) -> dict[str, str | int]:
    """Structured attachment ref (resolved to PDF bytes when sending)."""
    return {'kind': 'subscription_receipt', 'id': receipt.pk}


def _subscription_receipt_company_name(account) -> str:
    """Prefer the main company name over the tenant account label."""
    name = (
        Company.objects.filter(
            account_id=account.pk,
            is_main=True,
            deleted_at__isnull=True,
        )
        .order_by('id')
        .values_list('name', flat=True)
        .first()
    )
    if name and str(name).strip():
        return str(name).strip()
    return (account.name or 'Account').strip()


def _receipt_pdf_bytes(payment: SubscriptionPayment, receipt_number: str) -> bytes:
    account = payment.account
    company_name = _subscription_receipt_company_name(account)
    sub_row = payment.account_subscription
    plan = sub_row.subscription

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_x = 18 * mm
    content_w = width - (margin_x * 2)

    NAVY = colors.HexColor('#1a2b3c')
    NAVY_MID = colors.HexColor('#2c4154')
    SURFACE = colors.HexColor('#f8f9fb')
    BORDER = colors.HexColor('#dde2e8')
    TEXT = colors.HexColor('#1f2937')
    TEXT_MUTED = colors.HexColor('#6b7280')
    WHITE = colors.white

    issued_at = payment.paid_at.strftime('%b %d, %Y %I:%M %p')
    period = (
        f'{payment.period_start.isoformat()} – {payment.period_end.isoformat()}'
        if payment.period_end
        else payment.period_start.isoformat()
    )

    header_h = 34 * mm
    header_y = height - (12 * mm) - header_h
    pdf.setFillColor(NAVY)
    pdf.roundRect(margin_x, header_y, content_w, header_h, 8, stroke=0, fill=1)
    pdf.setFillColor(WHITE)
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(margin_x + (8 * mm), header_y + header_h - (11 * mm), 'SUBSCRIPTION RECEIPT')
    pdf.setFont('Helvetica', 10)
    pdf.drawRightString(
        margin_x + content_w - (8 * mm),
        header_y + header_h - (10.5 * mm),
        f'Receipt No: {receipt_number}',
    )
    pdf.drawRightString(
        margin_x + content_w - (8 * mm),
        header_y + header_h - (16.5 * mm),
        f'Issued: {issued_at}',
    )

    strip_h = 10 * mm
    strip_y = header_y - strip_h
    pdf.setFillColor(NAVY_MID)
    pdf.rect(margin_x, strip_y, content_w, strip_h, stroke=0, fill=1)
    pdf.setFillColor(WHITE)
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(margin_x + (8 * mm), strip_y + 3.2 * mm, company_name[:90])

    y = strip_y - (7 * mm)

    def section(title: str, rows: list[tuple[str, str]]) -> None:
        nonlocal y
        row_h = 7 * mm
        box_h = (len(rows) * row_h) + (9 * mm)
        box_y = y - box_h
        pdf.setFillColor(SURFACE)
        pdf.roundRect(margin_x, box_y, content_w, box_h, 6, stroke=0, fill=1)
        pdf.setStrokeColor(BORDER)
        pdf.roundRect(margin_x, box_y, content_w, box_h, 6, stroke=1, fill=0)
        pdf.setFillColor(TEXT)
        pdf.setFont('Helvetica-Bold', 11)
        pdf.drawString(margin_x + (6 * mm), box_y + box_h - (6.2 * mm), title)
        row_y = box_y + box_h - (12.5 * mm)
        for label, value in rows:
            pdf.setFillColor(TEXT_MUTED)
            pdf.setFont('Helvetica', 9)
            pdf.drawString(margin_x + (6 * mm), row_y, label)
            pdf.setFillColor(TEXT)
            pdf.setFont('Helvetica-Bold', 9)
            pdf.drawString(margin_x + (42 * mm), row_y, (value or '-')[:130])
            row_y -= row_h
        y = box_y - (4 * mm)

    section(
        'Subscription',
        [
            ('Plan', plan.name),
            ('Billing cycle', plan.get_billing_cycle_display()),
            ('Team seats', str(sub_row.team_seats)),
            ('Billing period', period),
            ('Description', payment.description or '-'),
        ],
    )
    section(
        'Payment',
        [
            ('Amount paid', _currency(payment.amount)),
            ('Currency', payment.currency),
            ('PayMongo invoice', payment.paymongo_invoice_id or '-'),
        ],
    )
    section(
        'Account',
        [
            ('Account', account.name or '-'),
            ('Contact email', account.contact_email or '-'),
        ],
    )

    pdf.setFillColor(TEXT_MUTED)
    pdf.setFont('Helvetica', 8)
    pdf.drawCentredString(
        width / 2,
        10 * mm,
        f'Generated by {company_name}.',
    )
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _receipt_storage_key(payment: SubscriptionPayment, receipt_number: str) -> str:
    return (
        f'subscription_receipts/account_{payment.account_id}/{receipt_number}.pdf'
    )


def _subscription_receipt_email_content(
    payment: SubscriptionPayment,
) -> tuple[str, str]:
    plan_name = payment.account_subscription.subscription.name
    subject = f'Your subscription receipt is ready – {plan_name}'
    body = (
        f'<p>Hello,</p>'
        f'<p>We received your subscription payment of {_currency(payment.amount)} '
        f'for <strong>{plan_name}</strong>.</p>'
        f'<p>Your receipt is attached to this email.</p>'
        f'<p>Thank you for using Planning With You.</p>'
    )
    return subject, body


def ensure_subscription_payment_receipt(
    payment_id: int,
    *,
    send_email: bool = True,
) -> SubscriptionReceipt | None:
    """
    Build the PDF receipt and email ``account.contact_email`` for a successful
    ``SubscriptionPayment`` row. Does nothing if the payment is missing.
    """
    payment = (
        SubscriptionPayment.objects.select_related(
            'account',
            'account_subscription',
            'account_subscription__subscription',
        )
        .filter(pk=payment_id)
        .first()
    )
    if payment is None or not payment_qualifies_for_receipt(payment):
        return None

    receipt_number = f'SPR-{payment.pk}'
    receipt, _ = SubscriptionReceipt.objects.get_or_create(
        payment_id=payment.pk,
        defaults={
            'account_id': payment.account_id,
            'receipt_number': receipt_number,
        },
    )

    if not receipt.receipt_url:
        key = _receipt_storage_key(payment, receipt_number)
        default_storage.save(key, ContentFile(_receipt_pdf_bytes(payment, receipt_number)))
        receipt.storage_key = key
        receipt.receipt_url = default_storage.url(key)
        receipt.receipt_number = receipt_number
        receipt.save(update_fields=['storage_key', 'receipt_url', 'receipt_number'])

    recipient = (payment.account.contact_email or '').strip()
    if send_email and recipient and receipt.emailed_at is None:
        subject, body = _subscription_receipt_email_content(payment)
        log = create_and_queue_email(
            to=[recipient],
            subject=subject,
            body=body,
            attachments=(
                [_subscription_receipt_attachment(receipt)]
                if (receipt.storage_key or '').strip()
                else []
            ),
            account=payment.account,
            company=None,
            created_by=None,
        )
        send_email_task.delay(log.pk)
        receipt.emailed_at = timezone.now()
        receipt.save(update_fields=['emailed_at'])

    return receipt
