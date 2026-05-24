"""Start PayMongo subscription checkout for an account."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from bookings.paymongo_client import PayMongoError, paymongo_configured
from users.models import Account, User

from .models import AccountSubscription, Subscription
from .paymongo_subscriptions import (
    create_customer,
    create_subscription,
    create_subscription_plan,
    subscription_checkout_url,
)
from .pricing import compute_subscription_pricing


class SubscriptionCheckoutError(Exception):
    pass


def _subscription_return_urls() -> tuple[str, str]:
    base = (getattr(settings, 'FRONTEND_URL', None) or '').rstrip('/')
    success_url = f'{base}/settings?tab=subscription&subscription=success'
    cancel_url = f'{base}/settings?tab=subscription&subscription=cancelled'
    return success_url, cancel_url


def _ensure_paymongo_customer(account: Account, user: User) -> str:
    existing = (account.paymongo_customer_id or '').strip()
    if existing:
        return existing
    customer = create_customer(
        email=user.email or account.contact_email,
        first_name=user.first_name or account.contact_person.split()[0] if account.contact_person else '',
        last_name=user.last_name or '',
        phone=account.contact_mobile_number,
        metadata={'account_id': str(account.pk)},
    )
    customer_id = str(customer.get('id') or '').strip()
    if not customer_id:
        raise PayMongoError('PayMongo did not return a customer id.')
    account.paymongo_customer_id = customer_id
    account.save(update_fields=['paymongo_customer_id', 'updated_at'])
    return customer_id


@transaction.atomic
def start_subscription_checkout(
    *,
    account: Account,
    user: User,
    subscription: Subscription,
    team_seats: int,
    discount_code: str = '',
) -> dict:
    if not paymongo_configured():
        raise SubscriptionCheckoutError(
            'PayMongo is not configured on the server.',
        )
    if subscription.plan == 'free' or not subscription.is_selectable:
        raise SubscriptionCheckoutError('This plan cannot be purchased.')
    if subscription.billing_cycle not in Subscription.BillingCycle.values:
        raise SubscriptionCheckoutError('Invalid billing cycle.')

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
    plan_label = (
        f'{subscription.name} · {pricing.users} user{"s" if pricing.users != 1 else ""} · '
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

    success_url, cancel_url = _subscription_return_urls()
    return {
        'checkout_url': checkout_url,
        'account_subscription_uuid': str(account_sub.uuid),
        'paymongo_subscription_id': paymongo_sub_id,
        'success_url': success_url,
        'cancel_url': cancel_url,
        'amount': str(pricing.total_price),
        'billing_cycle': subscription.billing_cycle,
        'plan': subscription.plan,
    }
