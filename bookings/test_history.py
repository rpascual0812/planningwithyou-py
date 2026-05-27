from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import (
    BookingGroup,
    BookingItem,
    BookingLine,
    BookingStatus,
    FormTemplate,
    History,
)
from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class BookingHistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.create(
            name='Philippines',
            iso_code='PHL',
            iso2_code='PH',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        cls.supplier_type = SupplierType.objects.create(name='Planner')

    def setUp(self):
        self.client = APIClient()
        self.account = Account.objects.create(
            name='Tenant',
            country=self.country,
            is_active=True,
        )
        self.company = Company.objects.create(
            account=self.account,
            name='Main Co',
            supplier_type=self.supplier_type,
            is_main=True,
            is_active=True,
        )
        self.status = BookingStatus.objects.create(
            account=self.account,
            title='New',
        )
        self.user = User.objects.create_user(
            username='editor@test.example',
            email='editor@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_create_booking_records_history(self):
        res = self.client.post(
            '/booking-items/',
            {
                'status': self.status.pk,
                'title': 'Wedding',
                'field_values': [
                    {
                        'label': 'Venue',
                        'field_type': 'text',
                        'value': 'Garden',
                        'group_name': 'Details',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        booking_id = res.json()['id']
        entry = History.objects.get(booking_id=booking_id, action=History.Action.CREATE)
        self.assertEqual(entry.actor_id, self.user.pk)
        self.assertEqual(entry.entity_type, History.EntityType.BOOKING)
        self.assertEqual(entry.resource_type, History.ResourceType.BOOKING)
        self.assertEqual(entry.resource_id, booking_id)
        self.assertIn('snapshot', entry.changes)

    def test_update_title_records_history(self):
        booking = BookingItem.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0099',
            title='Before',
        )
        res = self.client.patch(
            f'/booking-items/{booking.pk}/',
            {'title': 'After'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.filter(
            booking_id=booking.pk,
            action=History.Action.UPDATE,
        ).latest('created_at')
        self.assertEqual(entry.changes['booking']['title']['old'], 'Before')
        self.assertEqual(entry.changes['booking']['title']['new'], 'After')

    def test_replace_lines_records_replace_action(self):
        booking = BookingItem.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0100',
            title='Event',
        )
        group = BookingGroup.objects.create(booking=booking, name='Services')
        BookingLine.objects.create(
            account=self.account,
            booking=booking,
            booking_group=group,
            label='DJ',
            field_type='text',
            value='Old',
        )
        res = self.client.patch(
            f'/booking-items/{booking.pk}/',
            {
                'field_values': [
                    {
                        'label': 'DJ',
                        'field_type': 'text',
                        'value': 'New',
                        'group_name': 'Services',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.filter(
            booking_id=booking.pk,
            action=History.Action.REPLACE,
        ).latest('created_at')
        self.assertIn('lines', entry.changes)

    def test_history_list_endpoint(self):
        booking = BookingItem.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0101',
            title='Listed',
        )
        History.objects.create(
            account_id=self.account.pk,
            resource_type=History.ResourceType.BOOKING,
            resource_id=booking.pk,
            booking=booking,
            entity_type=History.EntityType.BOOKING,
            entity_id=booking.pk,
            action=History.Action.CREATE,
            actor=self.user,
            changes={'snapshot': {}},
        )
        res = self.client.get(f'/booking-items/{booking.pk}/history/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]['actor_name'], self.user.username)
        self.assertEqual(res.json()[0]['resource_type'], 'booking')

    def test_booking_status_update_records_history(self):
        res = self.client.patch(
            f'/booking-statuses/{self.status.pk}/',
            {'title': 'Confirmed', 'color': '#52b585'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.get(
            resource_type=History.ResourceType.BOOKING_STATUS,
            resource_id=self.status.pk,
            action=History.Action.UPDATE,
        )
        self.assertEqual(entry.changes['fields']['title']['old'], 'New')
        self.assertEqual(entry.changes['fields']['title']['new'], 'Confirmed')

    def test_booking_status_history_list_endpoint(self):
        History.objects.create(
            account_id=self.account.pk,
            resource_type=History.ResourceType.BOOKING_STATUS,
            resource_id=self.status.pk,
            entity_type=History.EntityType.BOOKING_STATUS,
            entity_id=self.status.pk,
            action=History.Action.UPDATE,
            actor=self.user,
            changes={'fields': {'title': {'old': 'A', 'new': 'B'}}},
        )
        res = self.client.get(f'/booking-statuses/{self.status.pk}/history/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)

    def test_form_template_update_records_history(self):
        template = FormTemplate.objects.create(
            account=self.account,
            company_id=self.company.id,
            name='Event Form',
            description='Old',
            is_active=True,
            is_default=False,
        )
        res = self.client.patch(
            f'/form-templates/{template.pk}/',
            {'description': 'New'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.get(
            resource_type=History.ResourceType.FORM_TEMPLATE,
            resource_id=template.pk,
            action=History.Action.UPDATE,
        )
        self.assertEqual(entry.changes['fields']['description']['old'], 'Old')
        self.assertEqual(entry.changes['fields']['description']['new'], 'New')

    def test_form_template_history_endpoint(self):
        template = FormTemplate.objects.create(
            account=self.account,
            company_id=self.company.id,
            name='My Form',
            is_active=True,
            is_default=False,
        )
        History.objects.create(
            account_id=self.account.pk,
            resource_type=History.ResourceType.FORM_TEMPLATE,
            resource_id=template.pk,
            entity_type=History.EntityType.FORM_TEMPLATE,
            entity_id=template.pk,
            action=History.Action.UPDATE,
            actor=self.user,
            changes={'fields': {'name': {'old': 'A', 'new': 'B'}}},
        )
        res = self.client.get(f'/form-templates/{template.pk}/history/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
