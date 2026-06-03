from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import History
from companies.models import Company
from countries.models import Country
from emails.models import EmailTemplate
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class EmailTemplateHistoryTests(TestCase):
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
        self.user = User.objects.create_user(
            username='editor@test.example',
            email='editor@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        self.template = EmailTemplate.objects.create(
            account=self.account,
            company=self.company,
            template_type=EmailTemplate.TemplateType.BOOKINGS,
            name='booking_update',
            title='Booking update',
            subject='Update',
            body='<p>Hello</p>',
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_update_email_template_records_history_without_quotation_id(self):
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.patch(
                f'/email-templates/quotations/{self.template.pk}/',
                {'body': '<p>Hi {first_name}</p>'},
                format='json',
            )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.get(
            resource_type=History.ResourceType.EMAIL_TEMPLATE,
            resource_id=self.template.pk,
            action=History.Action.UPDATE,
        )
        self.assertIsNone(entry.quotation_id)
        self.assertEqual(
            entry.changes['fields']['body']['new'],
            '<p>Hi {first_name}</p>',
        )
