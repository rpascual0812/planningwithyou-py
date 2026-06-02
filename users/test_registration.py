from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import BookingStatus, Tag
from calendars.models import CalendarStatus
from companies.models import Company
from config.models import Config
from config.views import BOOKINGS_GROUP_NAME_NAME, BOOKING_VIEW_NAME
from documents.models import DocumentFolder
from emails.models import EmailTemplate
from subscriptions.models import AccountSubscription, Subscription
from suppliers.models import SupplierType, Tier
from users.models import Account

User = get_user_model()


class RegisterApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.supplier_type = SupplierType.objects.create(name='Planner')
        Subscription.objects.create(
            plan='free',
            name='Free',
            billing_cycle='monthly',
            base_price=0,
            price_per_user=0,
        )

    def setUp(self):
        self.client = APIClient()

    def _payload(self, **overrides):
        data = {
            'company_name': 'Acme Events',
            'supplier_type_id': self.supplier_type.id,
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': 'jane@acme.test',
            'mobile_number': '+639171234567',
            'password': 'secret12',
        }
        data.update(overrides)
        return data

    @patch('users.views.send_email_task.delay')
    def test_register_creates_tenant_records(self, _mock_delay):
        response = self.client.post('/register/', self._payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('detail', response.data)
        self.assertNotIn('access', response.data)
        self.assertEqual(response.data['email'], 'jane@acme.test')

        account = Account.objects.get(name='Acme Events')
        self.assertTrue(account.is_active)
        self.assertEqual(account.country_id, 173)
        self.assertEqual(account.contact_person, 'Jane Doe')
        self.assertEqual(account.contact_email, 'jane@acme.test')
        self.assertEqual(account.contact_mobile_number, '+639171234567')

        sub = AccountSubscription.objects.get(account=account)
        self.assertEqual(sub.subscription.plan, 'free')
        self.assertEqual(sub.status, AccountSubscription.Status.ACTIVE)
        self.assertEqual(sub.team_seats, 1)
        self.assertIsNone(sub.end_date)
        self.assertEqual(sub.base_price, 0)
        self.assertEqual(sub.total_price, 0)

        company = Company.objects.get(account=account, is_main=True)
        self.assertEqual(company.name, 'Acme Events')
        self.assertEqual(company.supplier_type_id, self.supplier_type.id)
        self.assertEqual(company.timezone, 'Asia/Manila')
        self.assertEqual(company.mobile_number, '+639171234567')
        self.assertFalse(company.kyb_verified)

        titles = list(
            BookingStatus.objects.filter(account=account, company=company)
            .order_by('sort_order')
            .values_list('title', flat=True),
        )
        self.assertEqual(
            titles,
            ['New', 'Confirmed', 'In-progress', 'Completed', 'Cancelled'],
        )

        cal_titles = list(
            CalendarStatus.objects.filter(account=account)
            .order_by('sort_order')
            .values_list('title', flat=True),
        )
        self.assertEqual(
            cal_titles,
            [
                'Pending',
                'Confirmed',
                'Follow-up',
                'No Answer',
                'On Hold',
                'Completed',
                'Declined',
            ],
        )

        booking_view = Config.objects.get(
            account=account,
            scope='account',
            name=BOOKING_VIEW_NAME,
        )
        self.assertEqual(booking_view.value, 'list')

        group_name = Config.objects.get(
            account=account,
            scope='account',
            name=BOOKINGS_GROUP_NAME_NAME,
        )
        self.assertEqual(group_name.value, 'Group')

        tier_names = list(
            Tier.objects.filter(account=account, company=company)
            .order_by('name')
            .values_list('name', flat=True),
        )
        self.assertEqual(tier_names, ['Bronze', 'Gold', 'Silver'])

        template_names = set(
            EmailTemplate.objects.filter(account=account, company=company).values_list(
                'name',
                flat=True,
            ),
        )
        self.assertEqual(
            template_names,
            {'welcome', 'verify_email', 'password_reset', 'payment_link'},
        )

        tag_names = set(
            Tag.objects.filter(account=account, company=company).values_list(
                'tag',
                flat=True,
            ),
        )
        self.assertEqual(
            tag_names,
            {'new', 'confirmed', 'cancelled', 'completed', 'done'},
        )

        folder = DocumentFolder.objects.get(account=account, company=company)
        self.assertEqual(folder.name, 'General')

        user = User.objects.get(email='jane@acme.test')
        self.assertEqual(user.account_id, account.id)
        self.assertEqual(user.company_id, company.id)
        self.assertEqual(user.role.name, 'Owner')
        self.assertFalse(user.is_verified)
        self.assertTrue(user.check_password('secret12'))

    def test_register_rejects_duplicate_email(self):
        self.client.post('/register/', self._payload(), format='json')
        response = self.client.post(
            '/register/',
            self._payload(email='jane@acme.test', company_name='Other Co'),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
