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

from emails.mail import create_and_queue_email
from emails.models import EmailTemplate
from emails.tasks import send_email_task
from planningwithyou.template_placeholders import apply_template_placeholders

from .models import QuotationPayment, QuotationPaymentReceipt


def _currency(amount: Decimal) -> str:
    return f'PHP {amount:.2f}'


def _contact_lines(payment: QuotationPayment) -> list[str]:
    booking = payment.quotation
    contact = booking.contact
    if contact is None:
        return ['Name: -', 'Email: -']
    full_name = f'{contact.first_name} {contact.last_name}'.strip() or '-'
    return [
        f'Name: {full_name}',
        f'Email: {contact.email or "-"}',
        f'Company: {contact.company or "-"}',
    ]


def _receipt_pdf_bytes(payment: QuotationPayment, receipt_number: str) -> bytes:
    booking = payment.quotation
    company = payment.company
    created_by = booking.created_by

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

    issued_at = timezone.now().strftime('%b %d, %Y %I:%M %p')
    event_date = booking.date_of_event.strftime('%b %d, %Y %I:%M %p') if booking.date_of_event else '-'
    transaction_date = (
        payment.transaction_date.strftime('%b %d, %Y %I:%M %p')
        if payment.transaction_date
        else '-'
    )

    # Header band
    header_h = 34 * mm
    header_y = height - (12 * mm) - header_h
    pdf.setFillColor(NAVY)
    pdf.roundRect(margin_x, header_y, content_w, header_h, 8, stroke=0, fill=1)
    pdf.setFillColor(WHITE)
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(margin_x + (8 * mm), header_y + header_h - (11 * mm), 'PAYMENT RECEIPT')
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

    # Company strip
    strip_h = 10 * mm
    strip_y = header_y - strip_h
    pdf.setFillColor(NAVY_MID)
    pdf.rect(margin_x, strip_y, content_w, strip_h, stroke=0, fill=1)
    pdf.setFillColor(WHITE)
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(margin_x + (8 * mm), strip_y + 3.2 * mm, company.name[:90])

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
        'Quotation Information',
        [
            ('Quotation ID', str(booking.unique_id or booking.pk)),
            ('Quotation Title', booking.title or '-'),
            ('Event Date', event_date),
            ('Booked By', created_by.email if created_by else '-'),
        ],
    )
    contact_rows: list[tuple[str, str]] = []
    for entry in _contact_lines(payment):
        if ':' in entry:
            k, v = entry.split(':', 1)
            contact_rows.append((k.strip(), v.strip()))
    section('Contact', contact_rows or [('Name', '-'), ('Email', '-')])
    section(
        'Payment Details',
        [
            ('Transaction ID', payment.transaction_id or '-'),
            ('Transaction Status', (payment.transaction_status or '-').upper()),
            ('Payment Method', payment.payment_method or '-'),
            ('Transaction Date', transaction_date),
            ('Base Amount', _currency(payment.base_amount)),
            ('Charge Amount', _currency(payment.charge_amount)),
            ('Platform Fee', _currency(payment.platform_fee)),
            ('Processing Fee', _currency(payment.processing_fee)),
            ('Net Amount', _currency(payment.net_amount)),
        ],
    )

    # Footer
    pdf.setFillColor(TEXT_MUTED)
    pdf.setFont('Helvetica', 8)
    pdf.drawCentredString(
        width / 2,
        10 * mm,
        'Generated by Planning With You. This receipt confirms successful payment capture.',
    )

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _receipt_storage_key(payment: QuotationPayment, receipt_number: str) -> str:
    return (
        f'booking_payment_receipts/'
        f'account_{payment.account_id}/company_{payment.company_id}/{receipt_number}.pdf'
    )


def _payment_received_email_content(
    payment: QuotationPayment,
) -> tuple[str, str, EmailTemplate | None]:
    booking = payment.quotation
    template = (
        EmailTemplate.objects.filter(
            account_id=booking.account_id,
            company_id=booking.company_id,
            template_type=EmailTemplate.TemplateType.BOOKINGS,
            name='payment_received',
            is_active=True,
            deleted_at__isnull=True,
        )
        .order_by('-id')
        .first()
    )
    context = {
        'quotation_id': str(booking.unique_id or booking.pk),
        'quotation_title': booking.title or '',
        'transaction_id': payment.transaction_id or '',
        'amount_paid': _currency(payment.charge_amount),
    }
    if template is None:
        return (
            apply_template_placeholders(
                'Payment receipt for booking {quotation_id}',
                context,
            ),
            apply_template_placeholders(
                (
                    '<p>Your payment receipt is attached.</p>'
                    '<p>Quotation: {quotation_title}</p>'
                    '<p>Transaction ID: {transaction_id}</p>'
                    '<p>Amount paid: {amount_paid}</p>'
                ),
                context,
            ),
            None,
        )
    return (
        apply_template_placeholders(template.subject or '', context),
        apply_template_placeholders(template.body or '', context),
        template,
    )


def ensure_paid_booking_payment_receipt(payment_id: int) -> QuotationPaymentReceipt | None:
    payment = (
        QuotationPayment.objects.select_related('quotation', 'quotation__contact', 'quotation__created_by', 'company')
        .filter(pk=payment_id)
        .first()
    )
    if payment is None:
        return None
    if (payment.transaction_status or '').strip().lower() != 'paid':
        return None

    receipt, _ = QuotationPaymentReceipt.objects.get_or_create(
        quotation_payment_id=payment.pk,
        defaults={
            'quotation_id': payment.quotation_id,
            'account_id': payment.account_id,
            'company_id': payment.company_id,
        },
    )
    receipt_number = f'BPR-{payment.pk}'

    if not receipt.receipt_url:
        key = _receipt_storage_key(payment, receipt_number)
        default_storage.save(key, ContentFile(_receipt_pdf_bytes(payment, receipt_number)))
        receipt.storage_key = key
        receipt.receipt_url = default_storage.url(key)
        receipt.save(update_fields=['storage_key', 'receipt_url', 'updated_at'])

    _queue_payment_received_email(payment, receipt, use_contact_email=False)
    return receipt


def _payment_received_recipient(
    payment: QuotationPayment,
    *,
    use_contact_email: bool,
) -> str:
    if use_contact_email:
        contact = payment.quotation.contact
        return (getattr(contact, 'email', '') or '').strip() if contact else ''
    return (getattr(payment.quotation.created_by, 'email', '') or '').strip()


def _queue_payment_received_email(
    payment: QuotationPayment,
    receipt: QuotationPaymentReceipt,
    *,
    use_contact_email: bool,
) -> None:
    recipient = _payment_received_recipient(payment, use_contact_email=use_contact_email)
    if not recipient or receipt.emailed_at is not None:
        return
    subject, body, template = _payment_received_email_content(payment)
    attachments = [receipt.receipt_url] if receipt.receipt_url else []
    log = create_and_queue_email(
        to=[recipient],
        subject=subject,
        body=body,
        email_template=template,
        attachments=attachments,
        account=payment.quotation.account,
        company=payment.company,
        created_by=payment.quotation.created_by,
    )
    send_email_task.delay(log.pk)
    receipt.emailed_at = timezone.now()
    receipt.save(update_fields=['emailed_at', 'updated_at'])


def notify_payment_received(
    payment: QuotationPayment,
    *,
    use_contact_email: bool = False,
) -> QuotationPaymentReceipt | None:
    """Ensure receipt PDF exists and queue ``payment_received`` email."""
    if (payment.transaction_status or '').strip().lower() != 'paid':
        return None

    payment = (
        QuotationPayment.objects.select_related(
            'quotation',
            'quotation__contact',
            'quotation__created_by',
            'company',
        )
        .filter(pk=payment.pk)
        .first()
    )
    if payment is None:
        return None

    receipt, _ = QuotationPaymentReceipt.objects.get_or_create(
        quotation_payment_id=payment.pk,
        defaults={
            'quotation_id': payment.quotation_id,
            'account_id': payment.account_id,
            'company_id': payment.company_id,
        },
    )
    receipt_number = f'BPR-{payment.pk}'

    if not receipt.receipt_url:
        key = _receipt_storage_key(payment, receipt_number)
        default_storage.save(key, ContentFile(_receipt_pdf_bytes(payment, receipt_number)))
        receipt.storage_key = key
        receipt.receipt_url = default_storage.url(key)
        receipt.save(update_fields=['storage_key', 'receipt_url', 'updated_at'])

    _queue_payment_received_email(payment, receipt, use_contact_email=use_contact_email)
    return receipt
