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

from bookings.models import QuotationStatus, Tag
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
from subscriptions.lifecycle import get_subscription_catalog
from subscriptions.models import AccountSubscription
from suppliers.models import SupplierType, Tier

from .models import Account
from .roles import ensure_owner_role

User = get_user_model()

PHILIPPINES_COUNTRY_ID = 173

BOOKING_STATUSES = [
    ('New', '#1f3a5f'),
    ('Confirmed', '#52b585'),
    ('In-progress', '#5a8edb'),
    ('Completed', '#3a9870'),
    ('Cancelled', '#d65a5a'),
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
DEFAULT_COMPANY_TAGS = ('new', 'confirmed', 'cancelled', 'completed', 'done')

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
        'name': 'kyb_verified',
        'template_type': EmailTemplate.TemplateType.USERS,
        'title': 'Business verification approved',
        'subject': 'Your business verification is approved – {company_name}',
        'body': (
            '<h3>Hello,</h3>\n'
            '<p>Your Know Your Business (KYB) verification for '
            '<strong>{company_name}</strong> has been approved.</p>\n'
            '<p>You can now accept live payments through Planning With You.</p>\n'
            '<p>If you have questions, reply to this email.</p>\n'
            '<p>Thank you,<br>{company_name}</p>'
        ),
    },
    {
        'name': 'new_quotation',
        'template_type': EmailTemplate.TemplateType.BOOKINGS,
        'title': 'New Quote',
        'subject': '{company_name} - Quotation',
        'body': (
            '<p>Hi {first_name} {last_name},</p>'
            '<p>Please see the attached file/s</p>'
        ),
    },
    {
        'name': 'updated_quotation',
        'template_type': EmailTemplate.TemplateType.BOOKINGS,
        'title': 'Updated Quote',
        'subject': '{company_name} - Updated Quotation',
        'body': (
            '<p>Hi {first_name} {last_name},</p>'
            '<p>Please see the attached file/s</p>'
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
    {
        'name': 'payment_received',
        'template_type': EmailTemplate.TemplateType.BOOKINGS,
        'title': 'Payment Received',
        'subject': 'Payment receipt for booking {quotation_id}',
        'body': (
            '<p>Your payment receipt is attached.</p>'
            '<p>Quotation: {quotation_title}</p>'
            '<p>Transaction ID: {transaction_id}</p>'
            '<p>Amount paid: {amount_paid}</p>'
        ),
    },
    {
        'name': 'calendar_event_creation',
        'template_type': EmailTemplate.TemplateType.CALENDAR,
        'title': 'Scheduled Event',
        'subject': '{company_name} - Scheduled Event',
        'body': (
            '<p>Hi {first_name} {last_name},</p>'
            '<p>A new event has been scheduled:</p>'
            '<p>Title: {event_title}</p>'
            '<p>Start: {event_start}</p>'
            '<p>End: {event_end}</p>'
            '<p>Location: {event_location}</p>'
            '<p>Thank you.</p>'
        ),
    },
    {
        'name': 'calendar_event_updated',
        'template_type': EmailTemplate.TemplateType.CALENDAR,
        'title': 'Event Updated',
        'subject': '{company_name} - Event Updated',
        'body': (
            '<p>Hi {first_name} {last_name},</p>'
            '<p>An event has been updated:</p>'
            '<p>Title: {event_title}</p>'
            '<p>Start: {event_start}</p>'
            '<p>End: {event_end}</p>'
            '<p>Location: {event_location}</p>'
            '<p>Thank you.</p>'
        ),
    },
    # {
    #     'name': 'calendar_event_reminder',
    #     'template_type': EmailTemplate.TemplateType.CALENDAR,
    #     'title': 'Calendar Event Reminder',
    #     'subject': 'Calendar Event Reminder - {event_title}',
    #     'body': (
    #         '<p>Hi {first_name} {last_name},</p>'
    #         '<p>This is a reminder that the following event is scheduled for today:</p>'
    #         '<p>Event: {event_title}</p>'
    #         '<p>Date: {event_date}</p>'
    #         '<p>Time: {event_time}</p>'
    #         '<p>Location: {event_location}</p>'
    #         '<p>Thank you.</p>'
    #     ),
    # },
]


def seed_booking_statuses_for_company(account: Account, company: Company) -> None:
    """Default kanban columns for a company."""
    for sort_order, (title, color) in enumerate(BOOKING_STATUSES):
        if QuotationStatus.objects.filter(
            account=account,
            company=company,
            title__iexact=title,
        ).exists():
            continue
        QuotationStatus.objects.create(
            account=account,
            company=company,
            title=title,
            color=color,
            sort_order=sort_order,
        )


def seed_company_defaults(
    account: Account,
    company: Company,
    *,
    created_by=None,
) -> None:
    """Seed per-company defaults used by registration and manual company create."""
    seed_booking_statuses_for_company(account, company)

    for tag_name in DEFAULT_COMPANY_TAGS:
        if not Tag.objects.filter(
            account=account,
            company=company,
            tag__iexact=tag_name,
        ).exists():
            Tag.objects.create(
                account=account,
                company=company,
                tag=tag_name,
                created_by=created_by,
            )

    for tier_name in DEFAULT_TIERS:
        Tier.objects.get_or_create(
            account=account,
            company=company,
            name=tier_name,
            defaults={'is_active': True},
        )

    for template in EMAIL_TEMPLATES:
        EmailTemplate.objects.update_or_create(
            account=account,
            company=company,
            name=template['name'],
            defaults={
                **template,
                'is_active': True,
                'is_default': True,
            },
        )

    DocumentFolder.objects.get_or_create(
        account=account,
        company=company,
        name='General',
        defaults={'is_deleted': False},
    )


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

    free_subscription = get_subscription_catalog(plan='free', billing_cycle='monthly')
    if free_subscription is None:
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
        subscription=free_subscription,
        status=AccountSubscription.Status.ACTIVE,
        team_seats=1,
        start_date=today,
        end_date=None,
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
        contact_email=data.email.strip(),
        phone_number=data.phone_number.strip(),
        mobile_number=data.mobile_number.strip(),
        kyb_verified=False,
        max_bookings_per_day=1,
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

    seed_company_defaults(account, company)

    owner_role = ensure_owner_role(account)

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
        role=owner_role,
    )

    return RegistrationResult(account=account, company=company, user=user)
