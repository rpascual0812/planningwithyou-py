"""OpenAI chat completion helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class AiAssistantError(Exception):
    """Raised when the AI provider fails or returns invalid output."""


class AiAssistantNotConfigured(AiAssistantError):
    pass


def _client():
    api_key = getattr(settings, 'OPENAI_API_KEY', '').strip()
    if not api_key:
        raise AiAssistantNotConfigured('OPENAI_API_KEY is not configured.')
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AiAssistantNotConfigured(
            'Install the openai package to use AI assistant features.',
        ) from exc

    kwargs: dict[str, Any] = {'api_key': api_key}
    base_url = getattr(settings, 'OPENAI_API_BASE', '').strip()
    if base_url:
        kwargs['base_url'] = base_url
    timeout = getattr(settings, 'AI_ASSISTANT_TIMEOUT', 60)
    if timeout:
        kwargs['timeout'] = timeout
    return OpenAI(**kwargs)


def _openai_error_detail(exc: Exception) -> str | None:
    body = getattr(exc, 'body', None)
    if isinstance(body, dict):
        error = body.get('error')
        if isinstance(error, dict):
            message = error.get('message')
            if isinstance(message, str) and message.strip():
                return message.strip()[:300]
    message = getattr(exc, 'message', None)
    if isinstance(message, str) and message.strip():
        return message.strip()[:300]
    text = str(exc).strip()
    if text and text not in {repr(exc), type(exc).__name__}:
        return text[:300]
    return None


def _provider_error_message(exc: Exception) -> str:
    """Return a safe, actionable message for API failures."""
    try:
        from openai import (
            APIConnectionError,
            APITimeoutError,
            AuthenticationError,
            BadRequestError,
            NotFoundError,
            PermissionDeniedError,
            RateLimitError,
        )
    except ImportError:
        return 'AI provider request failed. Check server logs for details.'

    if isinstance(exc, AuthenticationError):
        return (
            'AI provider rejected the API key. '
            'Check OPENAI_API_KEY on the server.'
        )
    if isinstance(exc, PermissionDeniedError):
        return (
            'AI provider denied access. '
            'Verify billing and key permissions.'
        )
    if isinstance(exc, RateLimitError):
        return 'AI provider rate limit reached. Please try again in a moment.'
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return (
            'Could not reach the AI provider. '
            'Check network connectivity from the server.'
        )
    if isinstance(exc, NotFoundError):
        model = getattr(settings, 'AI_ASSISTANT_MODEL', 'gpt-4o-mini')
        return (
            f'AI model "{model}" was not found. '
            'Check AI_ASSISTANT_MODEL on the server.'
        )
    if isinstance(exc, BadRequestError):
        detail = _openai_error_detail(exc)
        if detail:
            return f'AI provider rejected the request: {detail}'
        return 'AI provider rejected the request. Check server logs for details.'

    detail = _openai_error_detail(exc)
    if detail:
        return f'AI provider request failed: {detail}'
    return 'AI provider request failed. Check server logs for details.'


def complete_json(
    *,
    system: str,
    user: str,
    model: str | None = None,
) -> tuple[dict[str, Any], dict[str, int | None]]:
    client = _client()
    model_name = (model or getattr(settings, 'AI_ASSISTANT_MODEL', 'gpt-4o-mini')).strip()
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            response_format={'type': 'json_object'},
            temperature=0.35,
        )
    except Exception as exc:
        logger.exception('AI assistant OpenAI request failed')
        raise AiAssistantError(_provider_error_message(exc)) from exc

    choice = response.choices[0].message.content if response.choices else None
    if not choice:
        raise AiAssistantError('AI provider returned an empty response.')

    try:
        payload = json.loads(choice)
    except json.JSONDecodeError as exc:
        raise AiAssistantError('AI provider returned invalid JSON.') from exc

    usage = response.usage
    usage_data = {
        'prompt_tokens': getattr(usage, 'prompt_tokens', None),
        'completion_tokens': getattr(usage, 'completion_tokens', None),
        'total_tokens': getattr(usage, 'total_tokens', None),
    }
    return payload, usage_data
