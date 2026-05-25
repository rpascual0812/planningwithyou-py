from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from bookings.paymongo_client import PayMongoError
from companies.models import Company
from countries.models import Country
from subscriptions.checkout import _ensure_paymongo_customer
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class EnsurePaymongoCustomerTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(
            name='Philippines',
            iso_code='PHL',
            iso2_code='PH',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        self.supplier_type = SupplierType.objects.create(name='Planner')
        self.account = Account.objects.create(
            name='Tenant',
            country=self.country,
            contact_email='billing@tenant.test',
        )
        self.company = Company.objects.create(
            account=self.account,
            name='Main Co',
            supplier_type=self.supplier_type,
            is_main=True,
            is_active=True,
        )
        self.user = User.objects.create_user(
            username='billing@tenant.test',
            email='billing@tenant.test',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )

    @patch('subscriptions.checkout.create_customer')
    @patch('subscriptions.checkout.find_customers_by_email')
    def test_reuses_existing_paymongo_customer_by_email(
        self,
        mock_find,
        mock_create,
    ):
        mock_find.return_value = [
            {'id': 'cus_existing123', 'type': 'customer', 'attributes': {}},
        ]
        customer_id = _ensure_paymongo_customer(self.account, self.user)
        self.assertEqual(customer_id, 'cus_existing123')
        mock_create.assert_not_called()
        self.account.refresh_from_db()
        self.assertEqual(self.account.paymongo_customer_id, 'cus_existing123')

    @patch('subscriptions.checkout.create_customer')
    @patch('subscriptions.checkout.find_customers_by_email')
    def test_duplicate_create_falls_back_to_lookup(
        self,
        mock_find,
        mock_create,
    ):
        mock_find.side_effect = [
            [],
            [{'id': 'cus_after_dup', 'type': 'customer', 'attributes': {}}],
        ]
        mock_create.side_effect = PayMongoError(
            'A customer with this email already exists',
            status_code=400,
        )
        customer_id = _ensure_paymongo_customer(self.account, self.user)
        self.assertEqual(customer_id, 'cus_after_dup')
        self.assertEqual(mock_find.call_count, 2)
        self.account.refresh_from_db()
        self.assertEqual(self.account.paymongo_customer_id, 'cus_after_dup')
