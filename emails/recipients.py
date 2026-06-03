"""Merge CC/BCC lists for outbound email (templates + explicit recipients)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import EmailTemplate


def merge_recipient_lists(
    *parts: Iterable[str] | None,
    exclude: Iterable[str] | None = None,
) -> list[str]:
    """Case-insensitive dedupe; ``exclude`` drops addresses already in To."""
    exclude_keys = {
        (e or '').strip().lower()
        for e in (exclude or [])
        if (e or '').strip()
    }
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        for raw in part:
            addr = (raw or '').strip()
            if not addr:
                continue
            key = addr.lower()
            if key in exclude_keys or key in seen:
                continue
            seen.add(key)
            out.append(addr)
    return out


def resolve_template_cc_bcc(
    email_template: EmailTemplate | None,
    *,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    exclude_to: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Combine explicit CC/BCC with those configured on an ``EmailTemplate``."""
    template_cc = list(email_template.cc or []) if email_template else []
    template_bcc = list(email_template.bcc or []) if email_template else []
    return (
        merge_recipient_lists(cc, template_cc, exclude=exclude_to),
        merge_recipient_lists(bcc, template_bcc, exclude=exclude_to),
    )
