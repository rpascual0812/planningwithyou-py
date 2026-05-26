from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import History
from companies.models import Company
from contacts.models import Contact
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class ContactHistoryTests(TestCase):
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
        self.contact = Contact.objects.create(
            account=self.account,
            company_org=self.company,
            first_name='Jane',
            last_name='Doe',
            email='jane@example.com',
        )
        self.client.force_authenticate(user=self.user)

    def test_update_contact_records_history(self):
        res = self.client.patch(
            f'/api/contacts/{self.contact.pk}/',
            {'first_name': 'Janet'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = History.objects.get(
            resource_type=History.ResourceType.CONTACT,
            resource_id=self.contact.pk,
            action=History.Action.UPDATE,
        )
        self.assertEqual(entry.changes['fields']['first_name']['old'], 'Jane')
        self.assertEqual(entry.changes['fields']['first_name']['new'], 'Janet')
