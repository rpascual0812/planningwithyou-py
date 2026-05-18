"""Read uploaded files without exposing storage paths in URLs."""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.urls import reverse

from bookings.models import BookingItem
from documents.models import Document

MAX_FILE_BYTES = 15 * 1024 * 1024

DOCUMENT_PROXY_RE = re.compile(r'/files/d/(\d+)/?', re.IGNORECASE)
BOOKING_PDF_PROXY_RE = re.compile(r'/files/b/(\d+)/pdf/?', re.IGNORECASE)


def parse_proxy_file_url(url: str) -> tuple[str, int] | None:
    """Return (kind, pk) for app file routes, or None."""
    from urllib.parse import urlparse

    path = urlparse(url).path
    match = DOCUMENT_PROXY_RE.search(path)
    if match:
        return 'document', int(match.group(1))
    match = BOOKING_PDF_PROXY_RE.search(path)
    if match:
        return 'booking_pdf', int(match.group(1))
    return None


def document_download_path(document_id: int) -> str:
    return reverse('secured-file-document', kwargs={'document_id': document_id})


def booking_pdf_download_path(booking_id: int) -> str:
    return reverse('secured-file-booking-pdf', kwargs={'booking_id': booking_id})


def booking_pdf_storage_key(booking: BookingItem) -> str:
    """S3/local storage object key (not a public URL)."""
    safe_id = (booking.unique_id or str(booking.pk)).replace('/', '-')
    return f'booking_pdfs/{booking.account_id}/{safe_id}.pdf'


def absolute_file_url(request, path: str) -> str:
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def document_file_url(document_id: int, request=None) -> str:
    return absolute_file_url(request, document_download_path(document_id))


def booking_pdf_file_url(booking_id: int, request=None) -> str:
    return absolute_file_url(request, booking_pdf_download_path(booking_id))


def api_public_base_url() -> str:
    explicit = getattr(settings, 'API_PUBLIC_BASE_URL', '').strip()
    if explicit:
        return explicit.rstrip('/')
    return 'http://localhost:8000'


def booking_pdf_api_url(booking_id: int) -> str:
    """Absolute secured download URL for use outside HTTP requests (e.g. Celery)."""
    return f'{api_public_base_url()}{booking_pdf_download_path(booking_id)}'


def _read_booking_pdf_bytes(stored: str) -> bytes:
    """Load PDF bytes from S3/local storage key, or legacy absolute path."""
    key = (stored or '').strip()
    if not key:
        raise FileNotFoundError('Booking PDF file not found')

    if default_storage.exists(key):
        with default_storage.open(key, 'rb') as handle:
            data = handle.read()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError('File exceeds size limit')
        return data

    legacy = Path(key)
    if legacy.is_file():
        data = legacy.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError('File exceeds size limit')
        return data

    raise FileNotFoundError('Booking PDF file not found')


def read_document_file(
    document_id: int,
    *,
    account_id: int | None = None,
) -> tuple[bytes, str, str]:
    qs = Document.objects.filter(pk=document_id, is_deleted=False)
    if account_id is not None:
        qs = qs.filter(account_id=account_id)
    doc = qs.first()
    if doc is None or not doc.file:
        raise FileNotFoundError('Document not found')

    with doc.file.open('rb') as handle:
        data = handle.read()
    if len(data) > MAX_FILE_BYTES:
        raise ValueError('File exceeds size limit')

    filename = doc.original_name or 'document'
    content_type = (
        doc.mime_type
        or mimetypes.guess_type(filename)[0]
        or 'application/octet-stream'
    )
    return data, filename, content_type


def read_booking_pdf_file(
    booking_id: int,
    *,
    account_id: int | None = None,
) -> tuple[bytes, str, str]:
    qs = BookingItem.objects.filter(pk=booking_id)
    if account_id is not None:
        qs = qs.filter(account_id=account_id)
    booking = qs.first()
    if booking is None:
        raise FileNotFoundError('Booking PDF not found')

    storage_key = booking_pdf_storage_key(booking)
    try:
        data = _read_booking_pdf_bytes(storage_key)
    except FileNotFoundError:
        legacy = (booking.pdf or '').strip()
        if legacy and not legacy.startswith(('http://', 'https://', '/')):
            data = _read_booking_pdf_bytes(legacy)
        else:
            raise FileNotFoundError('Booking PDF not found') from None
    safe_title = re.sub(r'[^\w\s-]+', '', booking.title or 'booking').strip() or 'booking'
    safe_title = re.sub(r'[-\s]+', '-', safe_title)[:80]
    filename = f'{safe_title}.pdf'
    return data, filename, 'application/pdf'


def read_file_from_proxy_url(
    url: str,
    *,
    account_id: int | None = None,
) -> tuple[bytes, str, str]:
    parsed = parse_proxy_file_url(url)
    if parsed is None:
        raise ValueError('Not a proxy file URL')
    kind, pk = parsed
    if kind == 'document':
        return read_document_file(pk, account_id=account_id)
    return read_booking_pdf_file(pk, account_id=account_id)
