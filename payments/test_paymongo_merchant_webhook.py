from unittest.mock import patch

from django.test import TestCase

from companies.models import Company, CompanyKybVerification
from countries.models import Country
from payments.models import PaymentIntegration
from payments.paymongo_merchant_webhook import handle_paymongo_merchant_webhook_event
from suppliers.models import SupplierType
from users.models import Account


def _merchant_event(event_type: str, merchant_id: str, *, reason: str = '') -> dict:
    attrs: dict = {
        'type': event_type,
        'data': {
            'id': merchant_id,
            'type': 'merchant',
            'attributes': {},
        },
    }
    if reason:
        attrs['rejection_reason'] = reason
    return {
        'type': event_type,
        'data': {
            'id': f'evt_{event_type.replace(".", "_")}',
            'attributes': attrs,
        },
    }


class PayMongoMerchantWebhookTests(TestCase):
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
            name='Verify Me Co',
            supplier_type=supplier_type,
            is_main=True,
            contact_email='contact@verifyme.test',
        )
        self.integration = PaymentIntegration.objects.create(
            company=self.company,
            account=self.account,
            paymongo_account_id='merch_123',
            activation_status='pending',
        )
        self.kyb = CompanyKybVerification.objects.create(
            company=self.company,
            paymongo_status=CompanyKybVerification.PaymongoStatus.DRAFT,
            paymongo_merchant_id='merch_123',
            merchant_business_name='Verify Me Co',
            merchant_email='owner@example.test',
            merchant_mobile_number='+639171234567',
        )

    def test_merchant_verified_marks_kyb_approved(self):
        handled = handle_paymongo_merchant_webhook_event(
            _merchant_event('merchant.verified', 'merch_123'),
        )
        self.assertTrue(handled)
        self.kyb.refresh_from_db()
        self.company.refresh_from_db()
        self.integration.refresh_from_db()
        self.assertEqual(self.kyb.paymongo_status, CompanyKybVerification.PaymongoStatus.APPROVED)
        self.assertTrue(self.company.kyb_verified)
        self.assertEqual(self.integration.activation_status, 'activated')

    @patch('companies.kyb_notifications.send_email_task.delay')
    @patch('companies.kyb_notifications.create_and_queue_email')
    def test_merchant_verified_emails_company_contact(
        self,
        mock_create_email,
        mock_send_task,
    ):
        mock_create_email.return_value = type('Log', (), {'pk': 99})()

        handle_paymongo_merchant_webhook_event(
            _merchant_event('merchant.verified', 'merch_123'),
        )

        mock_create_email.assert_called_once()
        kwargs = mock_create_email.call_args.kwargs
        self.assertEqual(kwargs['to'], ['contact@verifyme.test'])
        mock_send_task.assert_called_once_with(99)

    def test_account_activated_marks_kyb_approved(self):
        handled = handle_paymongo_merchant_webhook_event(
            _merchant_event('account.activated', 'merch_123'),
        )
        self.assertTrue(handled)
        self.kyb.refresh_from_db()
        self.company.refresh_from_db()
        self.assertEqual(self.kyb.paymongo_status, CompanyKybVerification.PaymongoStatus.APPROVED)
        self.assertTrue(self.company.kyb_verified)

    def test_merchant_rejected_marks_kyb_rejected(self):
        handled = handle_paymongo_merchant_webhook_event(
            _merchant_event(
                'merchant.rejected',
                'merch_123',
                reason='Missing supporting documents',
            ),
        )
        self.assertTrue(handled)
        self.kyb.refresh_from_db()
        self.company.refresh_from_db()
        self.assertEqual(self.kyb.paymongo_status, CompanyKybVerification.PaymongoStatus.REJECTED)
        self.assertFalse(self.company.kyb_verified)
        self.assertIn('Missing supporting documents', self.kyb.rejection_notes)

    def test_merchant_pending_marks_kyb_pending_paymongo(self):
        self.kyb.paymongo_status = CompanyKybVerification.PaymongoStatus.DRAFT
        self.kyb.save(update_fields=['paymongo_status', 'updated_at'])
        handled = handle_paymongo_merchant_webhook_event(
            _merchant_event('merchant.pending', 'merch_123'),
        )
        self.assertTrue(handled)
        self.kyb.refresh_from_db()
        self.assertEqual(
            self.kyb.paymongo_status,
            CompanyKybVerification.PaymongoStatus.PENDING_PAYMONGO,
        )
