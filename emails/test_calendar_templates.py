from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from emails.models import EmailTemplate
from suppliers.models import SupplierType
from users.models import Account
from users.registration import seed_company_defaults

User = get_user_model()


class EmailCalendarTemplateApiTests(TestCase):
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
        seed_company_defaults(self.account, self.company)
        self.user = User.objects.create_user(
            username='editor@test.example',
            email='editor@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_list_calendar_templates_for_company(self):
        res = self.client.get(
            '/email-templates/calendar/',
            {'company_id': self.company.pk},
        )
        self.assertEqual(res.status_code, 200)
        names = {row['name'] for row in res.data}
        self.assertIn('calendar_event_creation', names)
        self.assertIn('calendar_event_updated', names)
        self.assertTrue(all(row['type'] == 'calendar' for row in res.data))

    def test_create_calendar_template(self):
        res = self.client.post(
            '/email-templates/calendar/',
            {
                'name': 'custom_reminder',
                'title': 'Custom reminder',
                'subject': 'Reminder',
                'body': '<p>Hi</p>',
                'is_active': True,
                'company_id': self.company.pk,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['type'], 'calendar')
        tpl = EmailTemplate.objects.get(pk=res.data['id'])
        self.assertEqual(tpl.template_type, EmailTemplate.TemplateType.CALENDAR)
        self.assertFalse(tpl.is_default)

    def test_cannot_delete_default_calendar_template(self):
        tpl = EmailTemplate.objects.get(
            account=self.account,
            company=self.company,
            name='calendar_event_creation',
        )
        res = self.client.delete(f'/email-templates/calendar/{tpl.pk}/')
        self.assertEqual(res.status_code, 403)
