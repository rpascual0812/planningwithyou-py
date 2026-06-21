"""One subscription row per account: prepaid periods, scheduled downgrades, free defaults."""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from users.models import Account

from .errors import SubscriptionCheckoutError
from .models import AccountSubscription, Subscription
from .paymongo_subscriptions import cancel_paymongo_subscription
from .pricing import FREE_MAX_TEAM_SEATS, compute_subscription_pricing
from .proration import add_months, add_years

logger = logging.getLogger(__name__)

PLAN_RANK = {'free': 0, 'pro': 1, 'ai': 2}
PAID_PLAN_SLUGS = frozenset({'pro', 'ai'})


def plan_rank(plan_slug: str) -> int:
    return PLAN_RANK.get(plan_slug, 0)


def is_downgrade(current: Subscription, target: Subscription) -> bool:
    return plan_rank(target.plan) < plan_rank(current.plan)


def is_expired_paid_subscription(account_sub: AccountSubscription | None) -> bool:
    """True when a paid plan row is ACTIVE but its prepaid period has ended."""
    if account_sub is None:
        return False
    if account_sub.subscription.plan not in PAID_PLAN_SLUGS:
        return False
    if account_sub.status != AccountSubscription.Status.ACTIVE:
        return False
    if account_sub.end_date is None:
        return False
    return account_sub.end_date < timezone.localdate()


def should_offer_subscription_renewal(
    account_sub: AccountSubscription | None,
    subscription: Subscription,
    *,
    expired_paid_plan: str | None = None,
    renew_expired: bool = False,
) -> bool:
    """
    True when checkout should charge for a full renewal instead of 'no changes'.

    Covers expired prepaid rows, free rows after downgrade (``expired_paid_plan``),
    and a one-day slack when the client shows the plan as expired ahead of the server.
    """
    if account_sub is None or subscription.plan == 'free':
        return False

    expired_paid = expired_paid_plan or getattr(account_sub, '_expired_paid_plan', None)
    if account_sub.subscription.plan == 'free':
        return bool(expired_paid and subscription.plan == expired_paid)

    if account_sub.subscription.plan != subscription.plan:
        return False

    if is_expired_paid_subscription(account_sub):
        return True

    if account_sub.status != AccountSubscription.Status.ACTIVE:
        return True

    if account_sub.subscription.plan not in PAID_PLAN_SLUGS:
        return False

    if account_sub.end_date is None:
        return False

    today = timezone.localdate()
    if account_sub.end_date <= today:
        return True
    if renew_expired and account_sub.end_date <= today + timedelta(days=1):
        return True
    return False


def should_switch_to_free_plan(account_sub: AccountSubscription) -> bool:
    """True when a non-active paid plan row should be replaced with Free immediately."""
    if account_sub.subscription.plan not in PAID_PLAN_SLUGS:
        return False
    if account_sub.status == AccountSubscription.Status.ACTIVE:
        return False
    today = timezone.localdate()
    if account_sub.status == AccountSubscription.Status.PENDING:
        return account_sub.end_date is not None and account_sub.end_date < today
    return True


@transaction.atomic
def enforce_free_plan_if_inactive_or_expired(
    account_id: int,
) -> tuple[AccountSubscription | None, str | None]:
    """
    Downgrade inactive or expired Pro / AI Plus rows to Free.
    Returns (row after reconcile, expired paid plan slug if one was cleared).
    """
    row = get_account_subscription_row(account_id)
    if row is None or not should_switch_to_free_plan(row):
        return row, None

    expired_plan = row.subscription.plan
    free_sub = get_subscription_catalog(
        plan='free',
        billing_cycle=Subscription.BillingCycle.MONTHLY,
    )
    if free_sub is None:
        return row, expired_plan

    pricing = compute_subscription_pricing(free_sub, FREE_MAX_TEAM_SEATS)
    today = timezone.localdate()
    row.subscription = free_sub
    row.team_seats = pricing.team_seats
    row.base_price = pricing.base_price
    row.total_per_users = pricing.total_per_users
    row.total_price = pricing.total_price
    row.status = AccountSubscription.Status.ACTIVE
    row.reference_id = ''
    row.start_date = today
    row.end_date = None
    row.scheduled_subscription = None
    row.scheduled_team_seats = None
    row.save(
        update_fields=[
            'subscription',
            'team_seats',
            'base_price',
            'total_per_users',
            'total_price',
            'status',
            'reference_id',
            'start_date',
            'end_date',
            'scheduled_subscription',
            'scheduled_team_seats',
            'updated_at',
        ],
    )
    return row, expired_plan


def prepaid_period_end(subscription: Subscription, start: date) -> date | None:
    if subscription.plan == 'free':
        return None
    if subscription.billing_cycle == Subscription.BillingCycle.YEARLY:
        return add_years(start, 1)
    return add_months(start, 1)


def get_account_subscription_row(account_id: int) -> AccountSubscription | None:
    """Non-deleted subscription row for an account (any status)."""
    if not account_id:
        return None
    return (
        AccountSubscription.objects.filter(
            account_id=account_id,
            deleted_at__isnull=True,
        )
        .select_related('subscription', 'scheduled_subscription', 'account')
        .order_by('-start_date', '-id')
        .first()
    )


def get_account_subscription(account_id: int) -> AccountSubscription | None:
    if not account_id:
        return None
    today = timezone.localdate()
    return (
        AccountSubscription.objects.filter(
            account_id=account_id,
            deleted_at__isnull=True,
        )
        .filter(
            Q(status=AccountSubscription.Status.PENDING)
            | (
                Q(status=AccountSubscription.Status.ACTIVE)
                & (Q(end_date__isnull=True) | Q(end_date__gte=today))
            ),
        )
        .select_related('subscription', 'scheduled_subscription', 'account')
        .order_by('-start_date', '-id')
        .first()
    )


def get_subscription_catalog(
    *,
    plan: str,
    billing_cycle: str,
) -> Subscription | None:
    return Subscription.objects.filter(
        plan=plan,
        billing_cycle=billing_cycle,
        is_active=True,
    ).first()


def validate_team_seats(subscription: Subscription, team_seats: int) -> int:
    seats = max(1, team_seats)
    if subscription.plan == 'free' and seats > FREE_MAX_TEAM_SEATS:
        raise SubscriptionCheckoutError(
            f'The Free plan allows up to {FREE_MAX_TEAM_SEATS} user only.',
        )
    if not subscription.has_team_stepper and seats != subscription.default_users:
        seats = subscription.default_users
    return seats


@transaction.atomic
def apply_scheduled_changes_if_due(account_sub: AccountSubscription) -> bool:
    """Apply scheduled downgrade when prepaid period has ended."""
    if account_sub.scheduled_subscription_id is None:
        return False
    today = timezone.localdate()
    period_end = account_sub.end_date
    if period_end is not None and period_end > today:
        return False

    scheduled = account_sub.scheduled_subscription
    if scheduled is None:
        account_sub.scheduled_subscription = None
        account_sub.scheduled_team_seats = None
        account_sub.save(update_fields=['scheduled_subscription', 'scheduled_team_seats', 'updated_at'])
        return False

    seats = validate_team_seats(
        scheduled,
        account_sub.scheduled_team_seats or scheduled.default_users,
    )
    paymongo_id = (account_sub.reference_id or '').strip()
    if paymongo_id and scheduled.plan == 'free':
        try:
            cancel_paymongo_subscription(paymongo_id)
        except Exception as exc:
            logger.warning('PayMongo cancel failed for %s: %s', paymongo_id, exc)

    pricing = compute_subscription_pricing(scheduled, seats)
    today = timezone.localdate()
    account_sub.subscription = scheduled
    account_sub.team_seats = pricing.team_seats
    account_sub.base_price = pricing.base_price
    account_sub.total_per_users = pricing.total_per_users
    account_sub.total_price = pricing.total_price
    account_sub.scheduled_subscription = None
    account_sub.scheduled_team_seats = None
    account_sub.start_date = today
    account_sub.end_date = prepaid_period_end(scheduled, today)
    if scheduled.plan == 'free':
        account_sub.reference_id = ''
        account_sub.status = AccountSubscription.Status.ACTIVE
    account_sub.save(
        update_fields=[
            'subscription',
            'team_seats',
            'base_price',
            'total_per_users',
            'total_price',
            'scheduled_subscription',
            'scheduled_team_seats',
            'start_date',
            'end_date',
            'reference_id',
            'status',
            'updated_at',
        ],
    )
    return True


def current_account_subscription(account_id: int) -> AccountSubscription | None:
    row = get_account_subscription(account_id)
    if row is None:
        return None
    if apply_scheduled_changes_if_due(row):
        row = get_account_subscription(account_id)
    return row


def resolve_account_subscription_for_account(
    account_id: int,
) -> tuple[AccountSubscription | None, str | None]:
    """Apply free-plan enforcement for non-active rows; return active rows even if expired."""
    raw = get_account_subscription_row(account_id)
    expired_paid_plan: str | None = None
    if raw is not None and should_switch_to_free_plan(raw):
        if raw.subscription.plan in PAID_PLAN_SLUGS:
            expired_paid_plan = raw.subscription.plan
        enforce_free_plan_if_inactive_or_expired(account_id)
        raw = get_account_subscription_row(account_id)

    if raw is None:
        return None, None

    if raw.status == AccountSubscription.Status.ACTIVE:
        if apply_scheduled_changes_if_due(raw):
            raw = get_account_subscription_row(account_id)
        if raw is not None and expired_paid_plan:
            raw._expired_paid_plan = expired_paid_plan  # noqa: SLF001
        return raw, expired_paid_plan

    if raw.status == AccountSubscription.Status.PENDING:
        if expired_paid_plan:
            raw._expired_paid_plan = expired_paid_plan  # noqa: SLF001
        return raw, expired_paid_plan

    row = get_account_subscription(account_id) or raw
    if row is not None and expired_paid_plan:
        row._expired_paid_plan = expired_paid_plan  # noqa: SLF001
    return row, expired_paid_plan


@transaction.atomic
def ensure_account_subscription_row(
    *,
    account: Account,
    subscription: Subscription,
    team_seats: int = 1,
    status: str = AccountSubscription.Status.ACTIVE,
    reference_id: str = '',
) -> AccountSubscription:
    seats = validate_team_seats(subscription, team_seats)
    pricing = compute_subscription_pricing(subscription, seats)
    today = timezone.localdate()
    row = AccountSubscription.objects.filter(
        account=account,
        deleted_at__isnull=True,
    ).first()
    if row is None:
        return AccountSubscription.objects.create(
            uuid=uuid.uuid4(),
            account=account,
            subscription=subscription,
            status=status,
            team_seats=pricing.team_seats,
            start_date=today,
            end_date=prepaid_period_end(subscription, today),
            base_price=pricing.base_price,
            total_per_users=pricing.total_per_users,
            total_price=pricing.total_price,
            reference_id=reference_id,
        )
    if row:
        row.subscription = subscription
        row.team_seats = pricing.team_seats
        row.base_price = pricing.base_price
        row.total_per_users = pricing.total_per_users
        row.total_price = pricing.total_price
        row.status = status
        row.reference_id = reference_id or row.reference_id
        row.scheduled_subscription = None
        row.scheduled_team_seats = None
        row.save(
            update_fields=[
                'subscription',
                'team_seats',
                'base_price',
                'total_per_users',
                'total_price',
                'status',
                'reference_id',
                'scheduled_subscription',
                'scheduled_team_seats',
                'updated_at',
            ],
        )
    return row


@transaction.atomic
def activate_free_plan(
    *,
    account: Account,
    billing_cycle: str = Subscription.BillingCycle.MONTHLY,
) -> AccountSubscription:
    free_sub = get_subscription_catalog(plan='free', billing_cycle=billing_cycle)
    if free_sub is None:
        raise SubscriptionCheckoutError('Free plan is not available.')
    current = get_account_subscription(account.pk)
    if current and current.subscription.plan == 'free':
        raise SubscriptionCheckoutError('You are already on the Free plan.')
    if current and current.subscription.plan != 'free':
        return schedule_downgrade_to_free(account=account, billing_cycle=billing_cycle)
    return ensure_account_subscription_row(
        account=account,
        subscription=free_sub,
        team_seats=FREE_MAX_TEAM_SEATS,
        status=AccountSubscription.Status.ACTIVE,
        reference_id='',
    )


@transaction.atomic
def schedule_downgrade_to_free(
    *,
    account: Account,
    billing_cycle: str = Subscription.BillingCycle.MONTHLY,
) -> AccountSubscription:
    free_sub = get_subscription_catalog(plan='free', billing_cycle=billing_cycle)
    if free_sub is None:
        raise SubscriptionCheckoutError('Free plan is not available.')

    account_sub = get_account_subscription(account.pk)
    if account_sub is None:
        return ensure_account_subscription_row(
            account=account,
            subscription=free_sub,
            team_seats=FREE_MAX_TEAM_SEATS,
        )

    if account_sub.subscription.plan == 'free':
        raise SubscriptionCheckoutError('You are already on the Free plan.')

    account_sub.scheduled_subscription = free_sub
    account_sub.scheduled_team_seats = FREE_MAX_TEAM_SEATS
    account_sub.save(
        update_fields=['scheduled_subscription', 'scheduled_team_seats', 'updated_at'],
    )
    return account_sub


PREPAID_PERIOD_DAYS = 30


@transaction.atomic
def activate_paid_subscription(
    account_sub: AccountSubscription,
    *,
    subscription: Subscription | None = None,
    team_seats: int | None = None,
) -> None:
    """Mark a subscription active after successful payment; prepaid for 30 days."""
    if subscription is not None:
        seats = validate_team_seats(subscription, team_seats or account_sub.team_seats)
        pricing = compute_subscription_pricing(subscription, seats)
        account_sub.subscription = subscription
        account_sub.team_seats = pricing.team_seats
        account_sub.base_price = pricing.base_price
        account_sub.total_per_users = pricing.total_per_users
        account_sub.total_price = pricing.total_price

    today = timezone.localdate()
    account_sub.start_date = today
    account_sub.end_date = today + timedelta(days=PREPAID_PERIOD_DAYS)
    account_sub.status = AccountSubscription.Status.ACTIVE
    account_sub.scheduled_subscription = None
    account_sub.scheduled_team_seats = None
    account_sub.save(
        update_fields=[
            'subscription',
            'team_seats',
            'base_price',
            'total_per_users',
            'total_price',
            'start_date',
            'end_date',
            'status',
            'scheduled_subscription',
            'scheduled_team_seats',
            'updated_at',
        ],
    )


@transaction.atomic
def extend_prepaid_period(
    account_sub: AccountSubscription,
    *,
    paid_through: date | None = None,
) -> None:
    """Extend prepaid access after a successful recurring charge."""
    sub = account_sub.subscription
    anchor = account_sub.end_date or timezone.localdate()
    if paid_through and paid_through > anchor:
        account_sub.end_date = paid_through
    elif sub.plan != 'free':
        account_sub.end_date = prepaid_period_end(sub, anchor)
    account_sub.status = AccountSubscription.Status.ACTIVE
    account_sub.save(update_fields=['end_date', 'status', 'updated_at'])


@transaction.atomic
def start_prepaid_period(
    account_sub: AccountSubscription,
    subscription: Subscription,
    team_seats: int,
) -> None:
    seats = validate_team_seats(subscription, team_seats)
    pricing = compute_subscription_pricing(subscription, seats)
    today = timezone.localdate()
    account_sub.subscription = subscription
    account_sub.team_seats = pricing.team_seats
    account_sub.base_price = pricing.base_price
    account_sub.total_per_users = pricing.total_per_users
    account_sub.total_price = pricing.total_price
    account_sub.start_date = today
    account_sub.end_date = prepaid_period_end(subscription, today)
    account_sub.scheduled_subscription = None
    account_sub.scheduled_team_seats = None
    account_sub.save(
        update_fields=[
            'subscription',
            'team_seats',
            'base_price',
            'total_per_users',
            'total_price',
            'start_date',
            'end_date',
            'scheduled_subscription',
            'scheduled_team_seats',
            'updated_at',
        ],
    )
