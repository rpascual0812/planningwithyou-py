from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from bookings.models import Quotation, QuotationGroup, QuotationLine, QuotationPaymentLink, QuotationStatus
from bookings.notifications import (
    has_non_status_quotation_changes,
    send_new_quotation_email,
    send_payment_link_email,
    send_quotation_status_emails,
    send_updated_quotation_email,
)
from companies.models import Company
from contacts.models import Contact
from countries.models import Country
from planningwithyou.template_placeholders import (
    EMAIL_TEMPLATE_NEW_QUOTATION,
    EMAIL_TEMPLATE_PAYMENT_LINK,
    EMAIL_TEMPLATE_QUOTATION_STATUS_CONTACT,
    EMAIL_TEMPLATE_UPDATED_QUOTATION,
)
from suppliers.models import SupplierType
from users.models import Account
from users.registration import seed_company_defaults


class QuotationStatusNotificationTests(TestCase):
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
            name='Main Co',
            supplier_type=supplier_type,
            is_main=True,
            contact_email='main@example.test',
        )
        self.supplier = Company.objects.create(
            account=self.account,
            name='Supplier Co',
            supplier_type=supplier_type,
            contact_email='supplier@example.test',
        )
        seed_company_defaults(self.account, self.company)
        seed_company_defaults(self.account, self.supplier)

        self.status_new = QuotationStatus.objects.get(
            account=self.account,
            company=self.company,
            title='New',
        )
        self.status_confirmed = QuotationStatus.objects.get(
            account=self.account,
            company=self.company,
            title='Confirmed',
        )
        self.contact = Contact.objects.create(
            account=self.account,
            company_org=self.company,
            first_name='Jane',
            last_name='Client',
            email='client@example.test',
        )
        self.quotation = Quotation.objects.create(
            account=self.account,
            company=self.company,
            status=self.status_new,
            contact=self.contact,
            unique_id='26-0001',
            title='Wedding Package',
        )
        group = QuotationGroup.objects.create(
            quotation=self.quotation,
            name='Services',
        )
        QuotationLine.objects.create(
            account=self.account,
            quotation=self.quotation,
            quotation_group=group,
            company=self.supplier,
            label='Photographer',
            field_type='supplier',
            sort_order=0,
        )

    @patch('bookings.notifications.send_email_task.delay')
    @patch('bookings.notifications.create_and_queue_email')
    def test_status_change_sends_status_contact_to_contact(self, mock_create, mock_delay):
        mock_create.return_value = type('Log', (), {'pk': 1})()

        send_quotation_status_emails(
            self.quotation.pk,
            old_status_id=self.status_new.pk,
            new_status_id=self.status_confirmed.pk,
        )

        contact_call = mock_create.call_args_list[0]
        self.assertEqual(contact_call.kwargs['to'], ['client@example.test'])
        template = contact_call.kwargs['email_template']
        self.assertEqual(template.name, EMAIL_TEMPLATE_QUOTATION_STATUS_CONTACT)
        self.assertEqual(mock_create.call_count, 2)
        self.assertEqual(mock_delay.call_count, 2)

    @patch('bookings.notifications.send_email_task.delay')
    @patch('bookings.notifications.create_and_queue_email')
    def test_status_change_emails_line_companies_only(self, mock_create, mock_delay):
        mock_create.return_value = type('Log', (), {'pk': 1})()

        send_quotation_status_emails(
            self.quotation.pk,
            old_status_id=self.status_new.pk,
            new_status_id=self.status_confirmed.pk,
        )

        recipients = [call.kwargs['to'][0] for call in mock_create.call_args_list]
        self.assertIn('client@example.test', recipients)
        self.assertIn('supplier@example.test', recipients)
        self.assertNotIn('main@example.test', recipients)

    @patch('bookings.notifications.send_email_task.delay')
    @patch('bookings.notifications.create_and_queue_email')
    def test_new_quotation_email_to_contact_and_line_companies(self, mock_create, mock_delay):
        mock_create.return_value = type('Log', (), {'pk': 1})()

        send_new_quotation_email(self.quotation.pk)

        self.assertEqual(mock_create.call_count, 2)
        recipients = [call.kwargs['to'][0] for call in mock_create.call_args_list]
        self.assertIn('client@example.test', recipients)
        self.assertIn('supplier@example.test', recipients)
        template = mock_create.call_args_list[0].kwargs['email_template']
        self.assertEqual(template.name, EMAIL_TEMPLATE_NEW_QUOTATION)

    @patch('bookings.notifications.send_email_task.delay')
    @patch('bookings.notifications.create_and_queue_email')
    def test_updated_quotation_email_to_contact_and_line_companies(self, mock_create, mock_delay):
        mock_create.return_value = type('Log', (), {'pk': 1})()

        send_updated_quotation_email(self.quotation.pk)

        self.assertEqual(mock_create.call_count, 2)
        template = mock_create.call_args_list[0].kwargs['email_template']
        self.assertEqual(template.name, EMAIL_TEMPLATE_UPDATED_QUOTATION)

    @patch('bookings.notifications.send_email_task.delay')
    @patch('bookings.notifications.create_and_queue_email')
    def test_payment_link_email_to_contact(self, mock_create, mock_delay):
        link = QuotationPaymentLink.objects.create(
            quotation=self.quotation,
            account=self.account,
            company=self.company,
            public_token='11111111-1111-1111-1111-111111111111',
            base_amount='1000.00',
            platform_fee='0.00',
            processing_fee_estimate='0.00',
            charge_amount='1000.00',
            currency='PHP',
            expires_at=timezone.now() + timedelta(days=14),
        )
        mock_create.return_value = type('Log', (), {'pk': 2})()

        send_payment_link_email(self.quotation.pk, payment_link_id=link.pk)

        self.assertEqual(mock_create.call_args.kwargs['to'], ['client@example.test'])
        template = mock_create.call_args.kwargs['email_template']
        self.assertEqual(template.name, EMAIL_TEMPLATE_PAYMENT_LINK)
        self.assertIn('/pay/', mock_create.call_args.kwargs['body'])

    @patch('bookings.notifications.send_email_task.delay')
    @patch('bookings.notifications.create_and_queue_email')
    def test_skips_when_status_unchanged(self, mock_create, mock_delay):
        send_quotation_status_emails(
            self.quotation.pk,
            old_status_id=self.status_new.pk,
            new_status_id=self.status_new.pk,
        )
        mock_create.assert_not_called()
        mock_delay.assert_not_called()

    def test_has_non_status_changes_detects_title_change(self):
        self.assertTrue(
            has_non_status_quotation_changes(
                {'quotation': {'title': {'old': 'A', 'new': 'B'}}},
            ),
        )

    def test_has_non_status_changes_ignores_status_only(self):
        self.assertFalse(
            has_non_status_quotation_changes(
                {'quotation': {'status_id': {'old': 1, 'new': 2}}},
            ),
        )

    def test_has_non_status_changes_detects_line_changes(self):
        self.assertTrue(
            has_non_status_quotation_changes(
                {'lines': {'added': [{'label': 'Catering'}], 'removed': [], 'changed': []}},
            ),
        )
