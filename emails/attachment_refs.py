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
    read_booking_pdf_file,
    read_document_file,
    read_file_from_proxy_url,
)

ATTACHMENT_FETCH_TIMEOUT = 30
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024

DOCUMENT_REF_RE = re.compile(r'^document:(\d+)$')
BOOKING_PDF_REF_RE = re.compile(r'^booking_pdf:(\d+)$')


def normalize_attachment_item(item: Any) -> dict[str, Any]:
    """Persistable attachment reference (kind + id, or legacy url)."""
    if isinstance(item, dict):
        kind = str(item.get('kind') or item.get('type') or '').strip()
        if kind in {'document', 'booking_pdf'}:
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
        return _normalize_url_ref(text)

    raise ValueError(f'Unsupported attachment type: {type(item).__name__}')


def _storage_key_from_url(url: str) -> str | None:
    path = unquote(urlparse(url).path).lstrip('/')
    if not path:
        return None
    media_prefix = settings.MEDIA_URL.lstrip('/')
    if media_prefix and path.startswith(media_prefix):
        return path[len(media_prefix):].lstrip('/')
    if path.startswith(('documents/', 'booking_pdfs/')):
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


def attachment_public_url(item: Any, *, request=None) -> str:
    """URL for UI display (secured download route when possible)."""
    if isinstance(item, dict):
        kind = item.get('kind')
        if kind == 'document':
            return document_file_url(int(item['id']), request=request)
        if kind == 'booking_pdf':
            return booking_pdf_file_url(int(item['id']), request=request)
        if kind == 'url':
            return str(item.get('url') or '')
    if isinstance(item, str):
        parsed = parse_proxy_file_url(item)
        if parsed:
            kind, pk = parsed
            if kind == 'document':
                return document_file_url(pk, request=request)
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
