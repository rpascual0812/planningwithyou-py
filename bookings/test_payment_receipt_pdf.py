from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from bookings.models import Quotation, QuotationPayment, QuotationStatus
from bookings.payment_receipts import _receipt_pdf_bytes
from companies.models import Company
from contacts.models import Contact
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account
from users.registration import seed_company_defaults

User = get_user_model()


class PaymentReceiptPdfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        country = Country.objects.create(
            name='Philippines',
            iso_code='PHL',
            iso2_code='PH',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='Planner')
        cls.account = Account.objects.create(
            name='Planning With You Planner Suites',
            country=country,
        )
        cls.company = Company.objects.create(
            account=cls.account,
            name='Acme Events Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        seed_company_defaults(cls.account, cls.company)
        cls.user = User.objects.create_user(
            username='receipt@test.example',
            email='receipt@test.example',
            password='secret12',
            account=cls.account,
            company=cls.company,
            is_verified=True,
        )
        cls.status = QuotationStatus.objects.create(
            account=cls.account,
            company=cls.company,
            title='New',
        )
        cls.contact = Contact.objects.create(
            account=cls.account,
            company_org=cls.company,
            first_name='Jane',
            last_name='Doe',
            email='jane@example.com',
        )

    def test_receipt_pdf_uses_company_name_not_account_name(self):
        quotation = Quotation.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            contact=self.contact,
            title='Sample Event',
            created_by=self.user,
        )
        payment = QuotationPayment.objects.create(
            quotation=quotation,
            account_id=self.account.pk,
            company_id=self.company.pk,
            amount=Decimal('1000.00'),
            base_amount=Decimal('1000.00'),
            charge_amount=Decimal('1000.00'),
            transaction_status='paid',
            transaction_date=timezone.now(),
        )

        pdf_bytes = _receipt_pdf_bytes(payment, f'BPR-{payment.pk}')

        self.assertIn(b'Acme Events Co', pdf_bytes)
        self.assertNotIn(b'Planning With You Planner Suites', pdf_bytes)
