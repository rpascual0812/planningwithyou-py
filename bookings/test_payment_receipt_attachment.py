from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase
from django.utils import timezone

from bookings.models import Quotation, QuotationPayment, QuotationPaymentReceipt, QuotationStatus
from bookings.payment_receipts import _payment_receipt_attachment, _queue_payment_received_email
from companies.models import Company
from contacts.models import Contact
from countries.models import Country
from emails.attachment_refs import resolve_attachment_item
from emails.models import EmailLog
from suppliers.models import SupplierType
from users.models import Account
from users.registration import seed_company_defaults

User = get_user_model()


class PaymentReceiptAttachmentTests(TestCase):
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
        cls.account = Account.objects.create(name='Tenant', country=country)
        cls.company = Company.objects.create(
            account=cls.account,
            name='Acme Events Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        seed_company_defaults(cls.account, cls.company)
        cls.user = User.objects.create_user(
            username='attach@test.example',
            email='attach@test.example',
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

    def test_queue_email_stores_structured_attachment_not_s3_url(self):
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
        receipt = QuotationPaymentReceipt.objects.create(
            quotation_payment=payment,
            quotation=quotation,
            account_id=self.account.pk,
            company_id=self.company.pk,
            storage_key='booking_payment_receipts/test/BPR-1.pdf',
        )
        default_storage.save(receipt.storage_key, ContentFile(b'%PDF-test'))

        with patch('bookings.payment_receipts.send_email_task.delay'):
            _queue_payment_received_email(payment, receipt, use_contact_email=False)

        log = EmailLog.objects.latest('id')
        self.assertEqual(log.attachments, [_payment_receipt_attachment(receipt)])
        self.assertNotIn('http', str(log.attachments[0]))

    def test_resolve_payment_receipt_attachment_loads_pdf_bytes(self):
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
            transaction_id='pay_test_99',
            payment_method='card',
            transaction_status='paid',
            transaction_date=timezone.now(),
        )
        receipt = QuotationPaymentReceipt.objects.create(
            quotation_payment=payment,
            quotation=quotation,
            account_id=self.account.pk,
            company_id=self.company.pk,
            storage_key='booking_payment_receipts/test/pay_test_99_card.pdf',
        )
        default_storage.save(receipt.storage_key, ContentFile(b'%PDF-receipt'))

        raw, filename, content_type = resolve_attachment_item(
            _payment_receipt_attachment(receipt),
            account_id=self.account.pk,
            company_id=self.company.pk,
        )

        self.assertEqual(raw, b'%PDF-receipt')
        self.assertEqual(filename, 'pay_test_99_card.pdf')
        self.assertEqual(content_type, 'application/pdf')
