from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from bookings.models import Quotation, QuotationPayment, QuotationPaymentReceipt, QuotationStatus
from companies.models import Company
from contacts.models import Contact
from countries.models import Country
from emails.attachment_refs import attachment_download_filename
from emails.models import EmailLog
from emails.serializers import EmailLogSerializer
from suppliers.models import SupplierType
from users.models import Account
from users.registration import seed_company_defaults

User = get_user_model()


class AttachmentFilenameTests(TestCase):
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
            username='fname@test.example',
            email='fname@test.example',
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

    def test_payment_receipt_attachment_filename_uses_transaction_and_method(self):
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
            transaction_id='pay_live_001',
            payment_method='gcash',
            transaction_status='paid',
            transaction_date=timezone.now(),
        )
        receipt = QuotationPaymentReceipt.objects.create(
            quotation_payment=payment,
            quotation=quotation,
            account_id=self.account.pk,
            company_id=self.company.pk,
            storage_key='booking_payment_receipts/test/pay_live_001_gcash.pdf',
        )
        ref = {'kind': 'payment_receipt', 'id': receipt.pk}

        self.assertEqual(
            attachment_download_filename(ref, account_id=self.account.pk),
            'pay_live_001_gcash.pdf',
        )

    def test_email_log_serializer_includes_attachment_filename(self):
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
            amount=Decimal('500.00'),
            base_amount=Decimal('500.00'),
            charge_amount=Decimal('500.00'),
            transaction_id='pay_serial_01',
            payment_method='card',
            transaction_status='paid',
            transaction_date=timezone.now(),
        )
        receipt = QuotationPaymentReceipt.objects.create(
            quotation_payment=payment,
            quotation=quotation,
            account_id=self.account.pk,
            company_id=self.company.pk,
            storage_key='booking_payment_receipts/test/pay_serial_01_card.pdf',
        )
        log = EmailLog.objects.create(
            account=self.account,
            company=self.company,
            to=['a@b.com'],
            email_from='from@example.com',
            subject='Receipt',
            body='<p>Attached</p>',
            attachments=[{'kind': 'payment_receipt', 'id': receipt.pk}],
        )
        data = EmailLogSerializer(log).data
        self.assertEqual(len(data['attachments']), 1)
        self.assertIn('url', data['attachments'][0])
        self.assertIn('filename', data['attachments'][0])
        self.assertTrue(
            data['attachments'][0]['url'].endswith(f'/files/r/{receipt.pk}/pdf/'),
        )
        self.assertEqual(data['attachments'][0]['filename'], 'pay_serial_01_card.pdf')
