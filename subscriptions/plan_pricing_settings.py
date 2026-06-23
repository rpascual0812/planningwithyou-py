"""Pro, AI Plus, and Admin plan prices stored in the system settings table."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction

from system_settings.models import SystemSetting

from .models import Subscription
from .plans import ADMIN_PLAN, AI_PLAN, PRO_PLAN

PRO_BASE_PRICE_KEY = 'subscription_pro_base_price'
PRO_PRICE_PER_USER_KEY = 'subscription_pro_price_per_user'
AI_BASE_PRICE_KEY = 'subscription_ai_base_price'
AI_PRICE_PER_USER_KEY = 'subscription_ai_price_per_user'
ADMIN_BASE_PRICE_KEY = 'subscription_admin_base_price'
ADMIN_PRICE_PER_USER_KEY = 'subscription_admin_price_per_user'

PRICING_PLANS = (PRO_PLAN, AI_PLAN, ADMIN_PLAN)

DEFAULTS: dict[str, str] = {
    PRO_BASE_PRICE_KEY: '995.00',
    PRO_PRICE_PER_USER_KEY: '100.00',
    AI_BASE_PRICE_KEY: '1495.00',
    AI_PRICE_PER_USER_KEY: '150.00',
    ADMIN_BASE_PRICE_KEY: '995.00',
    ADMIN_PRICE_PER_USER_KEY: '100.00',
}

_PLAN_KEYS = {
    PRO_PLAN: (PRO_BASE_PRICE_KEY, PRO_PRICE_PER_USER_KEY),
    AI_PLAN: (AI_BASE_PRICE_KEY, AI_PRICE_PER_USER_KEY),
    ADMIN_PLAN: (ADMIN_BASE_PRICE_KEY, ADMIN_PRICE_PER_USER_KEY),
}


def _parse_amount(raw: str | None, *, default: str) -> Decimal:
    text = (raw or '').strip() or default
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f'Invalid amount: {text!r}') from exc
    return amount.quantize(Decimal('0.01'))


def _get_setting(name: str) -> str:
    row = SystemSetting.objects.filter(name=name).first()
    if row is None or not (row.value or '').strip():
        return DEFAULTS[name]
    return row.value.strip()


def _set_setting(name: str, value: str) -> None:
    SystemSetting.objects.update_or_create(
        name=name,
        defaults={'value': value},
    )


def plan_pricing_settings_payload() -> dict:
    """Current monthly base and per-user prices from ``system``."""
    pro_base = _parse_amount(_get_setting(PRO_BASE_PRICE_KEY), default=DEFAULTS[PRO_BASE_PRICE_KEY])
    pro_per_user = _parse_amount(
        _get_setting(PRO_PRICE_PER_USER_KEY),
        default=DEFAULTS[PRO_PRICE_PER_USER_KEY],
    )
    ai_base = _parse_amount(_get_setting(AI_BASE_PRICE_KEY), default=DEFAULTS[AI_BASE_PRICE_KEY])
    ai_per_user = _parse_amount(
        _get_setting(AI_PRICE_PER_USER_KEY),
        default=DEFAULTS[AI_PRICE_PER_USER_KEY],
    )
    admin_base = _parse_amount(
        _get_setting(ADMIN_BASE_PRICE_KEY),
        default=DEFAULTS[ADMIN_BASE_PRICE_KEY],
    )
    admin_per_user = _parse_amount(
        _get_setting(ADMIN_PRICE_PER_USER_KEY),
        default=DEFAULTS[ADMIN_PRICE_PER_USER_KEY],
    )
    return {
        'pro': {
            'base_price': str(pro_base),
            'price_per_user': str(pro_per_user),
        },
        'ai': {
            'base_price': str(ai_base),
            'price_per_user': str(ai_per_user),
        },
        'admin': {
            'base_price': str(admin_base),
            'price_per_user': str(admin_per_user),
        },
    }


@transaction.atomic
def update_plan_pricing_settings(
    *,
    pro_base_price: Decimal,
    pro_price_per_user: Decimal,
    ai_base_price: Decimal,
    ai_price_per_user: Decimal,
    admin_base_price: Decimal,
    admin_price_per_user: Decimal,
) -> dict:
    for amount in (
        pro_base_price,
        pro_price_per_user,
        ai_base_price,
        ai_price_per_user,
        admin_base_price,
        admin_price_per_user,
    ):
        if amount < 0:
            raise ValueError('Plan prices cannot be negative.')
    if pro_base_price <= 0:
        raise ValueError('Pro base price must be greater than zero.')
    if ai_base_price <= 0:
        raise ValueError('AI Plus base price must be greater than zero.')
    if admin_base_price <= 0:
        raise ValueError('Admin base price must be greater than zero.')

    _set_setting(PRO_BASE_PRICE_KEY, str(pro_base_price.quantize(Decimal('0.01'))))
    _set_setting(PRO_PRICE_PER_USER_KEY, str(pro_price_per_user.quantize(Decimal('0.01'))))
    _set_setting(AI_BASE_PRICE_KEY, str(ai_base_price.quantize(Decimal('0.01'))))
    _set_setting(AI_PRICE_PER_USER_KEY, str(ai_price_per_user.quantize(Decimal('0.01'))))
    _set_setting(ADMIN_BASE_PRICE_KEY, str(admin_base_price.quantize(Decimal('0.01'))))
    _set_setting(
        ADMIN_PRICE_PER_USER_KEY,
        str(admin_price_per_user.quantize(Decimal('0.01'))),
    )

    sync_subscription_plan_prices_from_system()
    return plan_pricing_settings_payload()


@transaction.atomic
def sync_subscription_plan_prices_from_system() -> bool:
    """
    Apply system-table prices to ``subscriptions`` rows for priced plans.
    Returns True when any row was updated.
    """
    payload = plan_pricing_settings_payload()
    changed = False
    for plan_slug in PRICING_PLANS:
        plan_values = payload[plan_slug]
        base_price = Decimal(plan_values['base_price'])
        price_per_user = Decimal(plan_values['price_per_user'])
        rows = Subscription.objects.filter(plan=plan_slug)
        for row in rows:
            if row.base_price == base_price and row.price_per_user == price_per_user:
                continue
            row.base_price = base_price
            row.price_per_user = price_per_user
            row.save(update_fields=['base_price', 'price_per_user', 'updated_at'])
            changed = True
    return changed
