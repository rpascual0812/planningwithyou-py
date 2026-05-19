"""Resize company logos and persist them on default storage (S3 or local media)."""

from __future__ import annotations

import os
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError

from planningwithyou.file_storage import (
    company_logo_api_url,
    company_logo_storage_key,
    delete_company_logo_storage,
)

MAX_LOGO_WIDTH = 400


def resize_logo_image(uploaded_file) -> ContentFile:
    """If image width exceeds 400px, scale down to 400px wide (height proportional)."""
    uploaded_file.seek(0)
    try:
        image = Image.open(uploaded_file)
        image.load()
    except UnidentifiedImageError as exc:
        raise ValueError('Invalid image file.') from exc

    image = ImageOps.exif_transpose(image)
    width, height = image.size
    if width > MAX_LOGO_WIDTH:
        new_height = max(1, round(height * MAX_LOGO_WIDTH / width))
        image = image.resize((MAX_LOGO_WIDTH, new_height), Image.Resampling.LANCZOS)

    original_name = getattr(uploaded_file, 'name', '') or 'logo.png'
    stem, ext = os.path.splitext(original_name)
    ext = ext.lower()

    buffer = BytesIO()
    if ext in {'.jpg', '.jpeg'}:
        if image.mode not in ('RGB',):
            image = image.convert('RGB')
        image.save(buffer, format='JPEG', quality=85, optimize=True)
        out_name = f'{stem}.jpg'
        content_type = 'image/jpeg'
    elif ext == '.webp':
        image.save(buffer, format='WEBP', quality=85)
        out_name = f'{stem}.webp'
        content_type = 'image/webp'
    elif ext == '.gif':
        image.save(buffer, format='GIF', optimize=True)
        out_name = f'{stem}.gif'
        content_type = 'image/gif'
    else:
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGBA')
        image.save(buffer, format='PNG', optimize=True)
        out_name = f'{stem}.png'
        content_type = 'image/png'

    buffer.seek(0)
    content = ContentFile(buffer.read(), name=out_name)
    content.content_type = content_type
    return content


def delete_company_logo(stored: str, *, account_id: int, company_id: int) -> None:
    """Remove logo bytes from storage (legacy key or by company id)."""
    key = (stored or '').strip()
    if key and not key.startswith(('http://', 'https://', '/')):
        try:
            if default_storage.exists(key):
                default_storage.delete(key)
        except OSError:
            pass
    delete_company_logo_storage(account_id, company_id)


def save_company_logo(
    account_id: int,
    company_id: int,
    uploaded_file,
    *,
    old_logo: str = '',
    request=None,
) -> str:
    """Resize, upload to storage, return secured API URL for ``companies.logo``."""
    content = resize_logo_image(uploaded_file)
    delete_company_logo(old_logo, account_id=account_id, company_id=company_id)

    key = company_logo_storage_key(account_id, company_id, content.name)
    if default_storage.exists(key):
        default_storage.delete(key)
    default_storage.save(key, content)

    return company_logo_api_url(company_id, request=request)
