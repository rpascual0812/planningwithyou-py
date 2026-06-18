"""Subscription and configuration gates for AI assistant features."""

from __future__ import annotations

from django.conf import settings

from subscriptions.account_plan import (
    active_subscription_plan_for_account,
    current_subscription_plan_for_account,
)


def ai_assistant_configured() -> bool:
    return bool(getattr(settings, 'OPENAI_API_KEY', '').strip())


def ai_assistant_plans() -> frozenset[str]:
    raw = getattr(settings, 'AI_ASSISTANT_PLANS', ('ai',))
    if isinstance(raw, str):
        parts = [item.strip() for item in raw.split(',') if item.strip()]
        return frozenset(parts)
    return frozenset(str(item).strip() for item in raw if str(item).strip())


def _account_plan_slugs(account_id: int) -> frozenset[str]:
    """Match UI subscription slug and active billing row when they differ."""
    return frozenset(
        {
            current_subscription_plan_for_account(account_id),
            active_subscription_plan_for_account(account_id),
        },
    )


def account_has_ai_assistant_plan(account_id: int | None) -> bool:
    if not account_id:
        return False
    allowed = ai_assistant_plans()
    return bool(_account_plan_slugs(account_id) & allowed)


def ai_assistant_available_for_user(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return account_has_ai_assistant_plan(getattr(user, 'account_id', None))
