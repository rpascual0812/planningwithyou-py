"""Resize profile photos and persist them on default storage (S3 or local media)."""

from __future__ import annotations

import os
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError

from planningwithyou.file_storage import (
    delete_user_photo_storage,
    user_photo_api_url,
    user_photo_storage_key,
)

PROFILE_PHOTO_SIZE = 200


def resize_profile_photo(uploaded_file) -> ContentFile:
    """Crop and scale to a 200×200 square."""
    uploaded_file.seek(0)
    try:
        image = Image.open(uploaded_file)
        image.load()
    except UnidentifiedImageError as exc:
        raise ValueError('Invalid image file.') from exc

    image = ImageOps.exif_transpose(image)
    image = ImageOps.fit(
        image,
        (PROFILE_PHOTO_SIZE, PROFILE_PHOTO_SIZE),
        method=Image.Resampling.LANCZOS,
    )

    original_name = getattr(uploaded_file, 'name', '') or 'photo.jpg'
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


def delete_user_photo(stored: str, *, account_id: int, user_id: int) -> None:
    key = (stored or '').strip()
    if key and not key.startswith(('http://', 'https://', '/')):
        try:
            if default_storage.exists(key):
                default_storage.delete(key)
        except OSError:
            pass
    delete_user_photo_storage(account_id, user_id)


def save_user_photo(
    account_id: int,
    user_id: int,
    uploaded_file,
    *,
    old_photo: str = '',
    request=None,
) -> str:
    content = resize_profile_photo(uploaded_file)
    delete_user_photo(old_photo, account_id=account_id, user_id=user_id)

    key = user_photo_storage_key(account_id, user_id, content.name)
    if default_storage.exists(key):
        default_storage.delete(key)
    default_storage.save(key, content)

    return user_photo_api_url(user_id, request=request)
