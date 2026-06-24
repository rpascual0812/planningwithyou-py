from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import (
    QuotationGroup,
    Quotation,
    QuotationLine,
    QuotationStatus,
    FormTemplate,
    History,
    Tag,
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
        self.status = QuotationStatus.objects.create(
            account=self.account,
            company=self.company,
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
            '/quotation-items/',
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
        quotation_id = res.json()['id']
        entry = History.objects.get(quotation_id=quotation_id, action=History.Action.CREATE)
        self.assertEqual(entry.actor_id, self.user.pk)
        self.assertEqual(entry.entity_type, History.EntityType.QUOTATION)
        self.assertEqual(entry.resource_type, History.ResourceType.QUOTATION)
        self.assertEqual(entry.resource_id, quotation_id)
        self.assertIn('snapshot', entry.changes)

    def test_update_title_records_history(self):
        booking = Quotation.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0099',
            title='Before',
        )
        res = self.client.patch(
            f'/quotation-items/{booking.pk}/',
            {'title': 'After'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.filter(
            quotation_id=booking.pk,
            action=History.Action.UPDATE,
        ).latest('created_at')
        self.assertEqual(entry.changes['quotation']['title']['old'], 'Before')
        self.assertEqual(entry.changes['quotation']['title']['new'], 'After')

    def test_replace_lines_records_replace_action(self):
        booking = Quotation.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0100',
            title='Event',
        )
        group = QuotationGroup.objects.create(quotation=booking, name='Services')
        QuotationLine.objects.create(
            account=self.account,
            quotation=booking,
            quotation_group=group,
            label='DJ',
            field_type='text',
            value='Old',
        )
        res = self.client.patch(
            f'/quotation-items/{booking.pk}/',
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
            quotation_id=booking.pk,
            action=History.Action.REPLACE,
        ).latest('created_at')
        self.assertIn('lines', entry.changes)

    def test_history_list_endpoint(self):
        booking = Quotation.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0101',
            title='Listed',
        )
        History.objects.create(
            account_id=self.account.pk,
            resource_type=History.ResourceType.QUOTATION,
            resource_id=booking.pk,
            quotation=booking,
            entity_type=History.EntityType.QUOTATION,
            entity_id=booking.pk,
            action=History.Action.CREATE,
            actor=self.user,
            changes={'snapshot': {}},
        )
        res = self.client.get(f'/quotation-items/{booking.pk}/history/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]['actor_name'], self.user.username)
        self.assertEqual(res.json()[0]['resource_type'], 'booking')

    def test_booking_status_update_records_history(self):
        res = self.client.patch(
            f'/quotation-statuses/{self.status.pk}/',
            {'title': 'Confirmed', 'color': '#52b585'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.get(
            resource_type=History.ResourceType.QUOTATION_STATUS,
            resource_id=self.status.pk,
            action=History.Action.UPDATE,
        )
        self.assertEqual(entry.changes['fields']['title']['old'], 'New')
        self.assertEqual(entry.changes['fields']['title']['new'], 'Confirmed')

    def test_booking_status_tag_update_records_history(self):
        tag_vip = Tag.objects.create(
            account=self.account,
            company=self.company,
            tag='vip',
            created_by=self.user,
        )
        tag_done = Tag.objects.create(
            account=self.account,
            company=self.company,
            tag='done',
            created_by=self.user,
        )
        self.status.tags.add(tag_vip)

        res = self.client.patch(
            f'/quotation-statuses/{self.status.pk}/',
            {'tag_ids': [tag_done.id]},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.get(
            resource_type=History.ResourceType.QUOTATION_STATUS,
            resource_id=self.status.pk,
            action=History.Action.UPDATE,
        )
        self.assertEqual(entry.changes['tags']['removed'], ['vip'])
        self.assertEqual(entry.changes['tags']['added'], ['done'])
        self.assertNotIn('fields', entry.changes)

    def test_booking_status_history_list_endpoint(self):
        History.objects.create(
            account_id=self.account.pk,
            resource_type=History.ResourceType.QUOTATION_STATUS,
            resource_id=self.status.pk,
            entity_type=History.EntityType.QUOTATION_STATUS,
            entity_id=self.status.pk,
            action=History.Action.UPDATE,
            actor=self.user,
            changes={'fields': {'title': {'old': 'A', 'new': 'B'}}},
        )
        res = self.client.get(f'/quotation-statuses/{self.status.pk}/history/')
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

    def test_form_template_create_defaults_company_id(self):
        res = self.client.post(
            '/form-templates/',
            {
                'name': 'New Form',
                'description': 'Details',
                'is_active': True,
                'is_default': False,
                'fields': [],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.content)
        template = FormTemplate.objects.get(pk=res.json()['id'])
        self.assertEqual(template.company_id, self.company.id)
        self.assertTrue(
            History.objects.filter(
                resource_type=History.ResourceType.FORM_TEMPLATE,
                resource_id=template.pk,
                action=History.Action.CREATE,
            ).exists(),
        )

    def test_form_template_supplier_field_persists_supplier_type(self):
        res = self.client.post(
            '/form-templates/',
            {
                'name': 'Supplier Form',
                'description': '',
                'is_active': True,
                'is_default': False,
                'fields': [
                    {
                        'label': 'Venue',
                        'field_type': 'supplier',
                        'is_required': True,
                        'supplier_type': self.supplier_type.pk,
                        'options': [],
                        'sort_order': 0,
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.content)
        field = res.json()['fields'][0]
        self.assertEqual(field['field_type'], 'supplier')
        self.assertEqual(field['supplier_type'], self.supplier_type.pk)
