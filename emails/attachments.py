"""Load email attachment bytes and build Mailjet attachment payloads."""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

from .attachment_refs import resolve_attachment_item

logger = logging.getLogger(__name__)

MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024


def _safe_filename(name: str) -> str:
    cleaned = os.path.basename(name).replace('\n', '').replace('\r', '').replace('"', '')
    return cleaned or 'attachment'


def build_mailjet_attachments(
    items: list[Any],
    *,
    account_id: int | None = None,
    company_id: int | None = None,
) -> tuple[list[dict], list[str]]:
    """
    Build Mailjet v3.1 attachment objects.

    Returns (attachments, errors) where errors lists entries that could not load.
    """
    attachments: list[dict] = []
    errors: list[str] = []
    used_names: dict[str, int] = {}

    for item in items:
        if item is None or item == '':
            continue
        try:
            raw, filename, content_type = resolve_attachment_item(
                item,
                account_id=account_id,
                company_id=company_id,
            )
            if len(raw) > MAX_ATTACHMENT_BYTES:
                raise ValueError('Attachment exceeds size limit')

            filename = _safe_filename(filename)
            count = used_names.get(filename, 0)
            used_names[filename] = count + 1
            if count:
                stem, dot, ext = filename.rpartition('.')
                filename = (
                    f'{stem}-{count + 1}.{ext}' if dot else f'{filename}-{count + 1}'
                )

            attachments.append({
                'ContentType': content_type,
                'Filename': filename,
                'Base64Content': base64.b64encode(raw).decode('ascii'),
            })
        except Exception as exc:
            logger.warning('Failed to load attachment %r: %s', item, exc)
            errors.append(f'{item!r} ({exc})')

    return attachments, errors
