"""Provision a new tenant (account, company, defaults) on self-service registration."""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from bookings.models import BookingStatus
from calendars.models import CalendarStatus
from companies.models import Company
from config.models import Config
from config.views import (
    BOOKINGS_GROUP_NAME_NAME,
    BOOKINGS_GROUP_NAME_SCOPE,
    BOOKING_VIEW_NAME,
    BOOKING_VIEW_SCOPE,
)
from documents.models import DocumentFolder
from emails.models import EmailTemplate
from subscriptions.models import AccountSubscription, Subscription
from suppliers.models import SupplierType, Tier

from .models import Account

User = get_user_model()

PHILIPPINES_COUNTRY_ID = 173
DEFAULT_SUBSCRIPTION_ID = 1

BOOKING_STATUSES = [
    ('New', '#1f3a5f'),
    ('Confirmed', '#52b585'),
    ('In-progress', '#5a8edb'),
    ('Cancelled', '#d65a5a'),
    ('Completed', '#3a9870'),
]

CALENDAR_STATUSES = [
    ('Pending', '#ffffff', '#f0a830'),
    ('Confirmed', '#ffffff', '#52b585'),
    ('Follow-up', '#ffffff', '#5a8edb'),
    ('No Answer', '#ffffff', '#fd7e14'),
    ('On Hold', '#ffffff', '#9c6cd0'),
    ('Completed', '#ffffff', '#1f3a5f'),
    ('Declined', '#ffffff', '#d65a5a'),
]

DEFAULT_TIERS = ('Bronze', 'Silver', 'Gold')

EMAIL_TEMPLATES = [
    {
        'name': 'welcome',
        'template_type': EmailTemplate.TemplateType.USERS,
        'title': 'Welcome!',
        'subject': 'Welcome to {company_name}!',
        'body': (
            '<h3>Hello {first_name},</h3>\n'
            '<p>An account has been created for you at {company_name}.</p>\n'
            '<div>\n'
            '<div>You will receive a separate email with your login details.</div>\n'
            '</div>'
        ),
    },
    {
        'name': 'verify_email',
        'template_type': EmailTemplate.TemplateType.USERS,
        'title': 'Verify your email',
        'subject': 'Verify your email – {company_name}',
        'body': (
            '<h3>Hello {first_name},</h3>\n'
            '<p>Thank you for registering with {company_name}.</p>\n'
            '<p>Please click the link below to verify your email address and sign in:</p>\n'
            '<p><a href="{verify_url}">{verify_url}</a></p>\n'
            '<p>This link expires in {lifetime} hours.</p>\n'
            '<p>If you did not create this account, you can safely ignore this email.</p>'
        ),
    },
    {
        'name': 'password_reset',
        'template_type': EmailTemplate.TemplateType.USERS,
        'title': 'Password Reset',
        'subject': 'Set Your Password – {company_name}',
        'body': (
            '<h3>Hello {first_name},</h3>\n'
            '<p>An account has been created for you at {company_name}.</p>\n'
            '<p>Please click the link below to set your password:</p>\n'
            '<p><a href="{reset_url}">{reset_url}</a></p>\n'
            '<p>This link expires in {lifetime} hours.</p>\n'
            '<p>If you did not expect this email, you can safely ignore it.</p>'
        ),
    },
    {
        'name': 'payment_link',
        'template_type': EmailTemplate.TemplateType.BOOKINGS,
        'title': 'Payment Link',
        'subject': 'Payment for your booking',
        'body': (
            '<p>Hello,</p>'
            '<p>Please complete your payment using the link below:</p>'
            '<p><a href="{payment_link}">{payment_link}</a></p>'
            '<p>Thank you.</p>'
        ),
    },
]


@dataclass(frozen=True)
class RegistrationInput:
    company_name: str
    supplier_type_id: int
    first_name: str
    last_name: str
    email: str
    mobile_number: str
    phone_number: str
    password: str


@dataclass
class RegistrationResult:
    account: Account
    company: Company
    user: User


def _add_one_month(start: date) -> date:
    month = start.month + 1
    year = start.year
    if month > 12:
        month = 1
        year += 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def _contact_person(first_name: str, last_name: str) -> str:
    return f'{first_name.strip()} {last_name.strip()}'.strip()


@transaction.atomic
def register_tenant(data: RegistrationInput) -> RegistrationResult:
    supplier_type = SupplierType.objects.filter(
        pk=data.supplier_type_id,
        is_active=True,
        deleted_at__isnull=True,
    ).first()
    if supplier_type is None:
        raise ValueError('Invalid company type.')

    if not Subscription.objects.filter(pk=DEFAULT_SUBSCRIPTION_ID).exists():
        raise ValueError('Default subscription is not configured.')

    if User.objects.filter(email__iexact=data.email).exists():
        raise ValueError('An account with this email already exists.')

    contact_person = _contact_person(data.first_name, data.last_name)
    today = timezone.localdate()

    account = Account.objects.create(
        name=data.company_name.strip(),
        is_active=True,
        country_id=PHILIPPINES_COUNTRY_ID,
        contact_person=contact_person,
        contact_email=data.email.strip(),
        contact_mobile_number=data.mobile_number.strip(),
    )

    AccountSubscription.objects.create(
        uuid=uuid.uuid4(),
        account=account,
        subscription_id=DEFAULT_SUBSCRIPTION_ID,
        status=AccountSubscription.Status.ACTIVE,
        team_seats=1,
        start_date=today,
        end_date=_add_one_month(today),
        base_price=Decimal('0'),
        total_per_users=Decimal('0'),
        total_price=Decimal('0'),
        discount_code='',
    )

    company = Company.objects.create(
        account=account,
        name=data.company_name.strip(),
        supplier_type=supplier_type,
        timezone='Asia/Manila',
        is_active=True,
        is_main=True,
        sort_order=0,
        contact_person=contact_person,
        phone_number=data.phone_number.strip(),
        mobile_number=data.mobile_number.strip(),
        kyb_verified=False,
        max_bookings_per_day=1,
    )

    for sort_order, (title, color) in enumerate(BOOKING_STATUSES):
        BookingStatus.objects.create(
            account=account,
            title=title,
            color=color,
            sort_order=sort_order,
        )

    for sort_order, (title, text_color, background_color) in enumerate(
        CALENDAR_STATUSES,
    ):
        CalendarStatus.objects.create(
            account=account,
            title=title,
            text_color=text_color,
            background_color=background_color,
            sort_order=sort_order,
        )

    Config.objects.create(
        account=account,
        scope=BOOKING_VIEW_SCOPE,
        name=BOOKING_VIEW_NAME,
        value='list',
    )
    Config.objects.create(
        account=account,
        scope=BOOKINGS_GROUP_NAME_SCOPE,
        name=BOOKINGS_GROUP_NAME_NAME,
        value='Group',
    )

    for tier_name in DEFAULT_TIERS:
        Tier.objects.create(
            account=account,
            company=company,
            name=tier_name,
            is_active=True,
        )

    for template in EMAIL_TEMPLATES:
        EmailTemplate.objects.create(
            account=account,
            company=company,
            is_active=True,
            is_default=True,
            **template,
        )

    DocumentFolder.objects.create(
        account=account,
        company=company,
        name='General',
    )

    username = data.email.strip().lower()
    user = User.objects.create_user(
        username=username,
        email=data.email.strip(),
        password=data.password,
        account=account,
        company=company,
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        is_active=True,
        is_verified=False,
        is_admin=False,
    )

    return RegistrationResult(account=account, company=company, user=user)
