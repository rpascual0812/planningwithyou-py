from django.test import TestCase

from companies.models import Company, CompanyKybVerification
from countries.models import Country
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
        )
        self.kyb = CompanyKybVerification.objects.create(
            company=self.company,
            status=CompanyKybVerification.Status.DRAFT,
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
        self.assertEqual(self.kyb.status, CompanyKybVerification.Status.APPROVED)

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
        self.assertEqual(self.kyb.status, CompanyKybVerification.Status.REJECTED)
        self.assertIn('Missing supporting documents', self.kyb.rejection_notes)

    def test_merchant_pending_marks_kyb_pending_paymongo(self):
        self.kyb.status = CompanyKybVerification.Status.DRAFT
        self.kyb.save(update_fields=['status', 'updated_at'])
        handled = handle_paymongo_merchant_webhook_event(
            _merchant_event('merchant.pending', 'merch_123'),
        )
        self.assertTrue(handled)
        self.kyb.refresh_from_db()
        self.assertEqual(
            self.kyb.status,
            CompanyKybVerification.Status.PENDING_PAYMONGO,
        )
