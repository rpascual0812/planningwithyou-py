"""Subscription plan slugs and shared helpers."""

from __future__ import annotations

FREE_PLAN = 'free'
PRO_PLAN = 'pro'
AI_PLAN = 'ai'
ADMIN_PLAN = 'admin'

PAID_PLAN_SLUGS = frozenset({PRO_PLAN, AI_PLAN, ADMIN_PLAN})
ADMIN_ONLY_PLANS = frozenset({ADMIN_PLAN})
LIFETIME_PLAN_SLUGS = frozenset({FREE_PLAN})

PLAN_RANK = {
    FREE_PLAN: 0,
    PRO_PLAN: 1,
    AI_PLAN: 2,
    ADMIN_PLAN: 3,
}


def plan_rank(plan_slug: str) -> int:
    return PLAN_RANK.get(plan_slug, 0)


def is_lifetime_plan(plan_slug: str) -> bool:
    return plan_slug in LIFETIME_PLAN_SLUGS


def is_admin_only_plan(plan_slug: str) -> bool:
    return plan_slug in ADMIN_ONLY_PLANS


def plan_grants_paid_features(plan_slug: str) -> bool:
    return plan_slug != FREE_PLAN


def user_may_view_plan(user, plan_slug: str) -> bool:
    if not is_admin_only_plan(plan_slug):
        return True
    from users.roles import has_platform_admin_read

    return has_platform_admin_read(user)
