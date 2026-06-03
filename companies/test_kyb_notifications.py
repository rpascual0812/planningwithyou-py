from unittest.mock import patch

from django.test import TestCase

from companies.kyb_notifications import send_company_kyb_approved_email
from companies.models import Company
from countries.models import Country
from emails.models import EmailTemplate
from suppliers.models import SupplierType
from users.models import Account, User
from users.registration import seed_company_defaults


class CompanyKybNotificationTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Peso',
            currency_symbol='P',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(name='Tenant', country=country)
        self.company = Company.objects.create(
            account=self.account,
            name='Notify Co',
            supplier_type=supplier_type,
            contact_email='billing@notifyco.test',
        )
        seed_company_defaults(self.account, self.company)

    @patch('companies.kyb_notifications.send_email_task.delay')
    @patch('companies.kyb_notifications.create_and_queue_email')
    def test_sends_to_company_contact_email(self, mock_create, mock_delay):
        mock_create.return_value = type('Log', (), {'pk': 1})()

        sent = send_company_kyb_approved_email(self.company.pk)

        self.assertTrue(sent)
        self.assertEqual(mock_create.call_args.kwargs['to'], ['billing@notifyco.test'])
        mock_delay.assert_called_once_with(1)

    @patch('companies.kyb_notifications.send_email_task.delay')
    @patch('companies.kyb_notifications.create_and_queue_email')
    def test_falls_back_to_first_user_email(self, mock_create, mock_delay):
        self.company.contact_email = ''
        self.company.save(update_fields=['contact_email'])
        User.objects.create_user(
            username='first@notifyco.test',
            email='first@notifyco.test',
            password='test-pass',
            account=self.account,
            company=self.company,
        )
        mock_create.return_value = type('Log', (), {'pk': 2})()

        sent = send_company_kyb_approved_email(self.company.pk)

        self.assertTrue(sent)
        self.assertEqual(mock_create.call_args.kwargs['to'], ['first@notifyco.test'])

    @patch('companies.kyb_notifications.send_email_task.delay')
    @patch('companies.kyb_notifications.create_and_queue_email')
    def test_applies_template_cc_bcc(self, mock_create, mock_delay):
        template = EmailTemplate.objects.get(
            account=self.account,
            company=self.company,
            name='kyb_verified',
        )
        template.cc = ['ops@notifyco.test']
        template.bcc = ['audit@notifyco.test']
        template.save(update_fields=['cc', 'bcc'])
        mock_create.return_value = type('Log', (), {'pk': 3})()

        send_company_kyb_approved_email(self.company.pk)

        self.assertEqual(
            mock_create.call_args.kwargs['email_template'],
            template,
        )
        mock_delay.assert_called_once_with(3)
