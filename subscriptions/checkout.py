"""Start PayMongo subscription checkout for an account."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from bookings.paymongo_client import PayMongoError, paymongo_configured
from users.models import Account, User

from .account_plan import active_paid_account_subscription
from .models import AccountSubscription, Subscription
from .paymongo_subscriptions import (
    create_customer,
    create_one_time_checkout,
    create_subscription,
    create_subscription_plan,
    customer_id_from_resource,
    duplicate_customer_email_error,
    find_customers_by_email,
    one_time_checkout_url,
    subscription_checkout_url,
    update_account_subscription_recurring_plan,
)
from .pricing import compute_subscription_pricing, plan_users
from .proration import (
    add_months,
    add_years,
    apply_subscription_selection,
    billing_period_end,
    checkout_amount_for_proration,
    compute_seat_upgrade_proration,
    same_plan_and_cycle,
)


class SubscriptionCheckoutError(Exception):
    pass


@dataclass(frozen=True)
class CheckoutQuote:
    checkout_kind: str
    amount_due_now: Decimal
    is_one_time_payment: bool
    next_billing_amount: Decimal
    next_billing_date: date | None
    team_seats: int
    additional_seats: int = 0


def _period_end_from_start(subscription: Subscription, start: date) -> date:
    if subscription.billing_cycle == Subscription.BillingCycle.YEARLY:
        return add_years(start, 1)
    return add_months(start, 1)


def _validate_checkout_inputs(subscription: Subscription, team_seats: int) -> int:
    if not paymongo_configured():
        raise SubscriptionCheckoutError(
            'PayMongo is not configured on the server.',
        )
    if subscription.plan == 'free' or not subscription.is_selectable:
        raise SubscriptionCheckoutError('This plan cannot be purchased.')
    if subscription.billing_cycle not in Subscription.BillingCycle.values:
        raise SubscriptionCheckoutError('Invalid billing cycle.')
    return max(1, team_seats)


def resolve_checkout_quote(
    *,
    account: Account,
    subscription: Subscription,
    team_seats: int,
) -> CheckoutQuote:
    team_seats = _validate_checkout_inputs(subscription, team_seats)
    pricing = compute_subscription_pricing(subscription, team_seats)
    active = active_paid_account_subscription(account.pk)

    if active and same_plan_and_cycle(active, subscription):
        next_date = billing_period_end(active)
        if team_seats < active.team_seats:
            return CheckoutQuote(
                checkout_kind='seat_reduction_only',
                amount_due_now=Decimal('0'),
                is_one_time_payment=False,
                next_billing_amount=pricing.total_price,
                next_billing_date=next_date,
                team_seats=pricing.team_seats,
            )
        if team_seats > active.team_seats:
            proration = compute_seat_upgrade_proration(
                subscription=subscription,
                current_seats=active.team_seats,
                new_seats=team_seats,
                period_start=active.start_date,
                period_end=next_date,
            )
            charge = checkout_amount_for_proration(proration.amount)
            kind = (
                'seat_upgrade_proration'
                if charge > 0
                else 'seat_upgrade_applied'
            )
            return CheckoutQuote(
                checkout_kind=kind,
                amount_due_now=charge,
                is_one_time_payment=charge > 0,
                next_billing_amount=pricing.total_price,
                next_billing_date=next_date,
                team_seats=pricing.team_seats,
                additional_seats=proration.additional_seats,
            )
        raise SubscriptionCheckoutError('No subscription changes to apply.')

    if active and (active.reference_id or '').strip():
        next_date = billing_period_end(active)
        return CheckoutQuote(
            checkout_kind='plan_change_only',
            amount_due_now=Decimal('0'),
            is_one_time_payment=False,
            next_billing_amount=pricing.total_price,
            next_billing_date=next_date,
            team_seats=pricing.team_seats,
        )

    today = timezone.localdate()
    return CheckoutQuote(
        checkout_kind='full_subscription',
        amount_due_now=pricing.total_price,
        is_one_time_payment=False,
        next_billing_amount=pricing.total_price,
        next_billing_date=_period_end_from_start(subscription, today),
        team_seats=pricing.team_seats,
    )


def checkout_quote_to_dict(quote: CheckoutQuote, subscription: Subscription) -> dict:
    return {
        'checkout_kind': quote.checkout_kind,
        'amount_due_now': str(quote.amount_due_now),
        'is_one_time_payment': quote.is_one_time_payment,
        'next_billing_amount': str(quote.next_billing_amount),
        'next_billing_date': (
            quote.next_billing_date.isoformat()
            if quote.next_billing_date
            else None
        ),
        'plan': subscription.plan,
        'billing_cycle': subscription.billing_cycle,
        'team_seats': quote.team_seats,
        'additional_seats': quote.additional_seats,
    }


def preview_subscription_checkout(
    *,
    account: Account,
    subscription: Subscription,
    team_seats: int,
) -> dict:
    quote = resolve_checkout_quote(
        account=account,
        subscription=subscription,
        team_seats=team_seats,
    )
    return checkout_quote_to_dict(quote, subscription)


def _subscription_return_urls() -> tuple[str, str]:
    base = (getattr(settings, 'FRONTEND_URL', None) or '').rstrip('/')
    success_url = f'{base}/settings?tab=subscription&subscription=success'
    cancel_url = f'{base}/settings?tab=subscription&subscription=cancelled'
    return success_url, cancel_url


def _checkout_response(
    *,
    checkout_kind: str,
    amount,
    subscription: Subscription,
    team_seats: int,
    checkout_url: str = '',
    account_subscription_uuid: str = '',
    paymongo_subscription_id: str = '',
) -> dict:
    success_url, cancel_url = _subscription_return_urls()
    return {
        'checkout_kind': checkout_kind,
        'checkout_url': checkout_url,
        'account_subscription_uuid': account_subscription_uuid,
        'paymongo_subscription_id': paymongo_subscription_id,
        'success_url': success_url,
        'cancel_url': cancel_url,
        'amount': str(amount),
        'billing_cycle': subscription.billing_cycle,
        'plan': subscription.plan,
        'team_seats': team_seats,
    }


def _save_paymongo_customer_id(account: Account, customer_id: str) -> str:
    account.paymongo_customer_id = customer_id
    account.save(update_fields=['paymongo_customer_id', 'updated_at'])
    return customer_id


def _ensure_paymongo_customer(account: Account, user: User) -> str:
    existing = (account.paymongo_customer_id or '').strip()
    if existing:
        return existing

    email = (user.email or account.contact_email or '').strip()
    if not email:
        raise SubscriptionCheckoutError('Account email is required for billing.')

    for row in find_customers_by_email(email):
        customer_id = customer_id_from_resource(row)
        if customer_id:
            return _save_paymongo_customer_id(account, customer_id)

    first_name = (
        user.first_name
        or (account.contact_person.split()[0] if account.contact_person else '')
    )
    last_name = user.last_name or ''
    try:
        customer = create_customer(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=account.contact_mobile_number,
            metadata={'account_id': str(account.pk)},
        )
    except PayMongoError as exc:
        if duplicate_customer_email_error(exc):
            for row in find_customers_by_email(email):
                customer_id = customer_id_from_resource(row)
                if customer_id:
                    return _save_paymongo_customer_id(account, customer_id)
        raise

    customer_id = customer_id_from_resource(customer)
    if not customer_id:
        raise PayMongoError('PayMongo did not return a customer id.')
    return _save_paymongo_customer_id(account, customer_id)


def _handle_plan_change(
    *,
    account_sub: AccountSubscription,
    subscription: Subscription,
    team_seats: int,
) -> dict:
    apply_subscription_selection(account_sub, subscription, team_seats)
    update_account_subscription_recurring_plan(account_sub, subscription, team_seats)
    return _checkout_response(
        checkout_kind='plan_change_only',
        amount=0,
        subscription=subscription,
        team_seats=account_sub.team_seats,
        account_subscription_uuid=str(account_sub.uuid),
        paymongo_subscription_id=account_sub.reference_id,
    )


def _handle_seat_reduction(
    *,
    account_sub: AccountSubscription,
    subscription: Subscription,
    team_seats: int,
) -> dict:
    apply_subscription_selection(account_sub, subscription, team_seats)
    update_account_subscription_recurring_plan(account_sub, subscription, team_seats)
    return _checkout_response(
        checkout_kind='seat_reduction_only',
        amount=0,
        subscription=subscription,
        team_seats=account_sub.team_seats,
        account_subscription_uuid=str(account_sub.uuid),
        paymongo_subscription_id=account_sub.reference_id,
    )


def _handle_seat_upgrade_with_proration(
    *,
    account: Account,
    user: User,
    account_sub: AccountSubscription,
    subscription: Subscription,
    team_seats: int,
) -> dict:
    proration = compute_seat_upgrade_proration(
        subscription=subscription,
        current_seats=account_sub.team_seats,
        new_seats=team_seats,
        period_start=account_sub.start_date,
        period_end=billing_period_end(account_sub),
    )
    charge = checkout_amount_for_proration(proration.amount)
    pricing = compute_subscription_pricing(subscription, team_seats)

    if charge <= 0:
        apply_subscription_selection(account_sub, subscription, team_seats)
        update_account_subscription_recurring_plan(account_sub, subscription, team_seats)
        return _checkout_response(
            checkout_kind='seat_upgrade_applied',
            amount=0,
            subscription=subscription,
            team_seats=account_sub.team_seats,
            account_subscription_uuid=str(account_sub.uuid),
            paymongo_subscription_id=account_sub.reference_id,
        )

    customer_id = _ensure_paymongo_customer(account, user)
    success_url, cancel_url = _subscription_return_urls()
    reference = f'sub-upgrade-{account_sub.uuid}-{uuid.uuid4().hex[:8]}'
    description = (
        f'Prorated add-on: {proration.additional_seats} user'
        f'{"s" if proration.additional_seats != 1 else ""} until '
        f'{proration.period_end.isoformat()}'
    )
    session = create_one_time_checkout(
        amount_php=charge,
        description=description,
        reference_number=reference[:255],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            'kind': 'subscription_seat_upgrade',
            'account_id': str(account.pk),
            'account_subscription_id': str(account_sub.pk),
            'account_subscription_uuid': str(account_sub.uuid),
            'subscription_id': str(subscription.pk),
            'team_seats': str(team_seats),
            'paymongo_customer_id': customer_id,
            'paymongo_subscription_id': account_sub.reference_id,
        },
    )
    checkout_url = one_time_checkout_url(session) or ''
    if not checkout_url:
        raise SubscriptionCheckoutError(
            'PayMongo did not return a checkout URL for the prorated payment.',
        )
    return _checkout_response(
        checkout_kind='seat_upgrade_proration',
        amount=charge,
        subscription=subscription,
        team_seats=team_seats,
        checkout_url=checkout_url,
        account_subscription_uuid=str(account_sub.uuid),
        paymongo_subscription_id=account_sub.reference_id,
    )


@transaction.atomic
def _start_full_subscription_checkout(
    *,
    account: Account,
    user: User,
    subscription: Subscription,
    team_seats: int,
    discount_code: str = '',
) -> dict:
    pricing = compute_subscription_pricing(subscription, team_seats)
    if pricing.total_price <= 0:
        raise SubscriptionCheckoutError('This plan does not require payment.')

    today = timezone.localdate()
    account_sub = AccountSubscription.objects.create(
        account=account,
        subscription=subscription,
        status=AccountSubscription.Status.PENDING,
        team_seats=pricing.team_seats,
        start_date=today,
        base_price=pricing.base_price,
        total_per_users=pricing.total_per_users,
        total_price=pricing.total_price,
        discount_code=(discount_code or '').strip(),
    )

    customer_id = _ensure_paymongo_customer(account, user)
    users = plan_users(subscription, pricing.team_seats)
    plan_label = (
        f'{subscription.name} · {users} user{"s" if users != 1 else ""} · '
        f'{subscription.get_billing_cycle_display()}'
    )
    plan = create_subscription_plan(
        name=plan_label,
        description=f'Planning With You {subscription.plan} subscription',
        amount_php=pricing.total_price,
        billing_cycle=subscription.billing_cycle,
        metadata={
            'kind': 'account_subscription',
            'account_id': str(account.pk),
            'account_subscription_uuid': str(account_sub.uuid),
            'subscription_id': str(subscription.pk),
            'plan_slug': subscription.plan,
            'billing_cycle': subscription.billing_cycle,
            'team_seats': str(pricing.team_seats),
        },
    )
    plan_id = str(plan.get('id') or '').strip()
    if not plan_id:
        raise PayMongoError('PayMongo did not return a plan id.')

    paymongo_sub = create_subscription(customer_id=customer_id, plan_id=plan_id)
    paymongo_sub_id = str(paymongo_sub.get('id') or '').strip()
    if not paymongo_sub_id:
        raise PayMongoError('PayMongo did not return a subscription id.')

    account_sub.reference_id = paymongo_sub_id
    account_sub.save(update_fields=['reference_id', 'updated_at'])

    checkout_url = subscription_checkout_url(paymongo_sub)
    if not checkout_url:
        raise SubscriptionCheckoutError(
            'PayMongo subscription was created but no checkout URL was returned. '
            'Complete card authorization in PayMongo or try again.',
        )

    return _checkout_response(
        checkout_kind='full_subscription',
        amount=pricing.total_price,
        subscription=subscription,
        team_seats=pricing.team_seats,
        checkout_url=checkout_url,
        account_subscription_uuid=str(account_sub.uuid),
        paymongo_subscription_id=paymongo_sub_id,
    )


def start_subscription_checkout(
    *,
    account: Account,
    user: User,
    subscription: Subscription,
    team_seats: int,
    discount_code: str = '',
) -> dict:
    team_seats = _validate_checkout_inputs(subscription, team_seats)
    active = active_paid_account_subscription(account.pk)

    if active and same_plan_and_cycle(active, subscription):
        if team_seats < active.team_seats:
            return _handle_seat_reduction(
                account_sub=active,
                subscription=subscription,
                team_seats=team_seats,
            )
        if team_seats > active.team_seats:
            return _handle_seat_upgrade_with_proration(
                account=account,
                user=user,
                account_sub=active,
                subscription=subscription,
                team_seats=team_seats,
            )
        raise SubscriptionCheckoutError(
            'No subscription changes to apply.',
        )

    if active and (active.reference_id or '').strip():
        return _handle_plan_change(
            account_sub=active,
            subscription=subscription,
            team_seats=team_seats,
        )

    return _start_full_subscription_checkout(
        account=account,
        user=user,
        subscription=subscription,
        team_seats=team_seats,
        discount_code=discount_code,
    )
