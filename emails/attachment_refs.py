"""Normalize and resolve email attachment references for sending."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.storage import default_storage

from planningwithyou.file_storage import (
    booking_pdf_file_url,
    document_file_url,
    parse_proxy_file_url,
    payment_receipt_file_url,
    read_booking_pdf_file,
    read_document_file,
    read_file_from_proxy_url,
    read_payment_receipt_file,
    read_subscription_receipt_file,
    subscription_receipt_file_url,
)

ATTACHMENT_FETCH_TIMEOUT = 30
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024

DOCUMENT_REF_RE = re.compile(r'^document:(\d+)$')
BOOKING_PDF_REF_RE = re.compile(r'^booking_pdf:(\d+)$')
PAYMENT_RECEIPT_REF_RE = re.compile(r'^payment_receipt:(\d+)$')
SUBSCRIPTION_RECEIPT_REF_RE = re.compile(r'^subscription_receipt:(\d+)$')


def normalize_attachment_item(item: Any) -> dict[str, Any]:
    """Persistable attachment reference (kind + id, or legacy url)."""
    if isinstance(item, dict):
        kind = str(item.get('kind') or item.get('type') or '').strip()
        if kind in {
            'document',
            'booking_pdf',
            'payment_receipt',
            'subscription_receipt',
        }:
            return {'kind': kind, 'id': int(item['id'])}
        if kind == 'url' and item.get('url'):
            return _normalize_url_ref(str(item['url']))
        raise ValueError(f'Unsupported attachment object: {item!r}')

    if isinstance(item, str):
        text = item.strip()
        if not text:
            raise ValueError('Empty attachment entry')
        doc_match = DOCUMENT_REF_RE.match(text)
        if doc_match:
            return {'kind': 'document', 'id': int(doc_match.group(1))}
        booking_match = BOOKING_PDF_REF_RE.match(text)
        if booking_match:
            return {'kind': 'booking_pdf', 'id': int(booking_match.group(1))}
        payment_receipt_match = PAYMENT_RECEIPT_REF_RE.match(text)
        if payment_receipt_match:
            return {'kind': 'payment_receipt', 'id': int(payment_receipt_match.group(1))}
        subscription_receipt_match = SUBSCRIPTION_RECEIPT_REF_RE.match(text)
        if subscription_receipt_match:
            return {
                'kind': 'subscription_receipt',
                'id': int(subscription_receipt_match.group(1)),
            }
        return _normalize_url_ref(text)

    raise ValueError(f'Unsupported attachment type: {type(item).__name__}')


def _storage_key_from_url(url: str) -> str | None:
    path = unquote(urlparse(url).path).lstrip('/')
    if not path:
        return None
    media_prefix = settings.MEDIA_URL.lstrip('/')
    if media_prefix and path.startswith(media_prefix):
        return path[len(media_prefix):].lstrip('/')
    if path.startswith(
        (
            'documents/',
            'quotation_pdfs/',
            'booking_payment_receipts/',
        ),
    ):
        return path
    return None


def _read_local_media_file(url: str) -> bytes | None:
    path = unquote(urlparse(url).path)
    marker = '/media/'
    if marker not in path:
        return None
    rel = path.split(marker, 1)[1].lstrip('/')
    if not rel:
        return None
    local_path = Path(settings.MEDIA_ROOT) / rel
    if local_path.is_file():
        data = local_path.read_bytes()
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise ValueError('Attachment exceeds size limit')
        return data
    return None


def _read_from_storage(url: str) -> bytes | None:
    key = _storage_key_from_url(url)
    if not key:
        return None
    try:
        if default_storage.exists(key):
            with default_storage.open(key, 'rb') as handle:
                data = handle.read()
            if len(data) > MAX_ATTACHMENT_BYTES:
                raise ValueError('Attachment exceeds size limit')
            return data
    except OSError:
        return None
    return None


def _fetch_http(url: str) -> bytes:
    request = Request(url, headers={'User-Agent': 'planningwithyou-mail/1.0'})
    with urlopen(request, timeout=ATTACHMENT_FETCH_TIMEOUT) as response:
        data = response.read()
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ValueError('Attachment exceeds size limit')
    return data


def load_attachment_bytes(url: str, *, account_id: int | None = None) -> bytes:
    """Load legacy attachment URLs (S3, media, or HTTP)."""
    cleaned = url.strip()
    if not cleaned:
        raise ValueError('Empty attachment URL')

    if parse_proxy_file_url(cleaned):
        data, _, _ = read_file_from_proxy_url(cleaned, account_id=account_id)
        return data

    for loader in (_read_local_media_file, _read_from_storage):
        data = loader(cleaned)
        if data is not None:
            return data

    return _fetch_http(cleaned)


def _normalize_url_ref(url: str) -> dict[str, Any]:
    parsed = parse_proxy_file_url(url)
    if parsed:
        kind, pk = parsed
        return {'kind': kind, 'id': pk}
    return {'kind': 'url', 'url': url}


def _filename_from_url_path(url: str) -> str:
    base = unquote(urlparse(url).path.rstrip('/').rsplit('/', 1)[-1])
    if base and base.lower() != 'pdf':
        return base if '.' in base else f'{base}.pdf'
    return 'attachment.pdf'


def attachment_download_filename(
    item: Any,
    *,
    account_id: int | None = None,
    company_id: int | None = None,
) -> str:
    """Human-facing attachment filename without loading file bytes."""
    if isinstance(item, dict):
        kind = item.get('kind')
        if kind == 'document':
            from documents.models import Document

            doc = Document.objects.filter(pk=int(item['id']), is_deleted=False).first()
            if doc is not None:
                return doc.original_name or 'document'
        if kind == 'booking_pdf':
            from bookings.models import Quotation

            booking = Quotation.objects.filter(pk=int(item['id'])).first()
            if booking is not None:
                safe_title = re.sub(
                    r'[^\w\s-]+',
                    '',
                    booking.title or 'booking',
                ).strip() or 'booking'
                safe_title = re.sub(r'[-\s]+', '-', safe_title)[:80]
                return f'{safe_title}.pdf'
        if kind == 'payment_receipt':
            from bookings.models import QuotationPaymentReceipt
            from bookings.payment_receipts import payment_receipt_filename

            receipt = (
                QuotationPaymentReceipt.objects.select_related('quotation_payment')
                .filter(pk=int(item['id']))
                .first()
            )
            if receipt is not None and receipt.quotation_payment is not None:
                return payment_receipt_filename(receipt.quotation_payment)
        if kind == 'subscription_receipt':
            from subscriptions.models import SubscriptionReceipt

            receipt = SubscriptionReceipt.objects.filter(pk=int(item['id'])).first()
            if receipt is not None:
                return f'{receipt.receipt_number or receipt.pk}.pdf'
        if kind == 'url':
            return _filename_from_url_path(str(item.get('url') or ''))

    if isinstance(item, str):
        text = item.strip()
        parsed = parse_proxy_file_url(text)
        if parsed:
            kind, pk = parsed
            return attachment_download_filename(
                {'kind': kind, 'id': pk},
                account_id=account_id,
                company_id=company_id,
            )
        key = _storage_key_from_url(text)
        if key:
            base = key.rsplit('/', 1)[-1]
            if base:
                return base
        return _filename_from_url_path(text)

    return 'attachment.pdf'


def attachment_public_url(item: Any, *, request=None) -> str:
    """URL for UI display (secured download route when possible)."""
    if isinstance(item, dict):
        kind = item.get('kind')
        if kind == 'document':
            return document_file_url(int(item['id']), request=request)
        if kind == 'booking_pdf':
            return booking_pdf_file_url(int(item['id']), request=request)
        if kind == 'payment_receipt':
            return payment_receipt_file_url(int(item['id']), request=request)
        if kind == 'subscription_receipt':
            return subscription_receipt_file_url(int(item['id']), request=request)
        if kind == 'url':
            return str(item.get('url') or '')
    if isinstance(item, str):
        parsed = parse_proxy_file_url(item)
        if parsed:
            kind, pk = parsed
            if kind == 'document':
                return document_file_url(pk, request=request)
            if kind == 'payment_receipt':
                return payment_receipt_file_url(pk, request=request)
            if kind == 'subscription_receipt':
                return subscription_receipt_file_url(pk, request=request)
            return booking_pdf_file_url(pk, request=request)
        return item
    return ''


def resolve_attachment_item(
    item: Any,
    *,
    account_id: int | None = None,
    company_id: int | None = None,
) -> tuple[bytes, str, str]:
    """Load bytes, filename, and content type for one attachment entry."""
    if isinstance(item, dict):
        kind = item.get('kind')
        if kind == 'document':
            return read_document_file(
                int(item['id']),
                account_id=account_id,
                company_id=company_id,
            )
        if kind == 'booking_pdf':
            return read_booking_pdf_file(
                int(item['id']),
                account_id=account_id,
                company_id=company_id,
            )
        if kind == 'payment_receipt':
            return read_payment_receipt_file(
                int(item['id']),
                account_id=account_id,
                company_id=company_id,
            )
        if kind == 'subscription_receipt':
            return read_subscription_receipt_file(
                int(item['id']),
                account_id=account_id,
            )
        if kind == 'url':
            url = str(item.get('url') or '').strip()
            raw = load_attachment_bytes(url, account_id=account_id)
            filename = url.rstrip('/').rsplit('/', 1)[-1] or 'attachment'
            return raw, filename, _guess_type(filename)

    if isinstance(item, str):
        text = item.strip()
        parsed = parse_proxy_file_url(text)
        if parsed:
            return read_file_from_proxy_url(
                text,
                account_id=account_id,
                company_id=company_id,
            )
        raw = load_attachment_bytes(text, account_id=account_id)
        filename = text.rstrip('/').rsplit('/', 1)[-1] or 'attachment'
        return raw, filename, _guess_type(filename)

    raise ValueError(f'Unsupported attachment entry: {item!r}')


def _guess_type(filename: str) -> str:
    import mimetypes

    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'
