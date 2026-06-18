"""Prompt templates and response shaping for quotation AI actions."""

from __future__ import annotations

from .client import complete_json
from .quotation_context import format_quotation_context_for_prompt


SUMMARY_SYSTEM = (
    'You are a professional event-planning assistant for Planning With You. '
    'Summarize quotations clearly for planners preparing for client calls. '
    'Respond with JSON: {"summary": string, "highlights": string[]}. '
    'Use 2-4 short highlight bullets. Be factual; do not invent prices or dates.'
)

EMAIL_SYSTEM = (
    'You are a professional event-planning assistant for Planning With You. '
    'Draft client-facing email copy for a quotation. '
    'Respond with JSON: {"subject": string, "body_html": string}. '
    'body_html must be simple HTML using p, strong, ul, li, and a tags only. '
    'Do not include a signature block with placeholders the app already merges. '
    'Be warm and professional. Mention the quotation reference when helpful. '
    'If payment or balance details are relevant, include them accurately from context.'
)


def summarize_quotation(context: dict, *, user_prompt: str = '') -> tuple[dict, dict]:
    details = format_quotation_context_for_prompt(context)
    extra = (user_prompt or '').strip()
    user_message = details
    if extra:
        user_message += f'\n\nAdditional instructions:\n{extra}'
    payload, usage = complete_json(system=SUMMARY_SYSTEM, user=user_message)
    summary = (payload.get('summary') or '').strip()
    highlights = payload.get('highlights') or []
    if not summary:
        raise ValueError('AI did not return a summary.')
    if not isinstance(highlights, list):
        highlights = []
    cleaned_highlights = [
        str(item).strip() for item in highlights if str(item).strip()
    ]
    return (
        {'summary': summary, 'highlights': cleaned_highlights},
        usage,
    )


def draft_quotation_email(context: dict, *, user_prompt: str = '') -> tuple[dict, dict]:
    details = format_quotation_context_for_prompt(context)
    extra = (user_prompt or '').strip()
    user_message = details
    if extra:
        user_message += f'\n\nAdditional instructions:\n{extra}'
    payload, usage = complete_json(system=EMAIL_SYSTEM, user=user_message)
    subject = (payload.get('subject') or '').strip()
    body_html = (payload.get('body_html') or '').strip()
    if not subject or not body_html:
        raise ValueError('AI did not return a complete email draft.')
    return (
        {'subject': subject, 'body_html': body_html},
        usage,
    )
