from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from emails.models import EmailLog
from suppliers.models import SupplierType
from users.models import Account
from users.registration import seed_company_defaults

User = get_user_model()


class EmailAttachmentDownloadTests(TestCase):
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
            username='email@test.example',
            email='email@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    @patch('emails.views.resolve_attachment_item')
    def test_download_attachment_streams_file(self, mock_resolve):
        mock_resolve.return_value = (b'%PDF-1.4', 'quote.pdf', 'application/pdf')
        log = EmailLog.objects.create(
            account=self.account,
            company=self.company,
            to=['a@b.com'],
            email_from='from@example.com',
            subject='Quote',
            body='<p>Hi</p>',
            attachments=[{'kind': 'booking_pdf', 'id': 42}],
        )

        res = self.client.get(f'/emails/{log.pk}/attachments/0/?download=1')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, b'%PDF-1.4')
        self.assertIn('quote.pdf', res['Content-Disposition'])
        mock_resolve.assert_called_once_with(
            {'kind': 'booking_pdf', 'id': 42},
            account_id=self.account.pk,
            company_id=self.company.pk,
        )

    def test_download_attachment_missing_index_returns_404(self):
        log = EmailLog.objects.create(
            account=self.account,
            company=self.company,
            to=['a@b.com'],
            email_from='from@example.com',
            subject='Quote',
            body='<p>Hi</p>',
            attachments=[],
        )

        res = self.client.get(f'/emails/{log.pk}/attachments/0/?download=1')

        self.assertEqual(res.status_code, 404)
