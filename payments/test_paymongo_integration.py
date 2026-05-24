from django.test import TestCase, override_settings

from companies.models import Company
from config.models import Country
from payments.models import PaymentIntegration
from payments.paymongo_config import (
    company_can_accept_paymongo_payments,
    get_paymongo_company_context,
    paymongo_configured,
)
from suppliers.models import SupplierType
from users.models import Account, User


class PayMongoPlatformConfigTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(name='Tenant', country=country)
        self.company = Company.objects.create(
            account=self.account,
            name='Pay Co',
            supplier_type=supplier_type,
            is_main=True,
            kyb_verified=True,
        )

    @override_settings(
        PAYMONGO_SECRET_KEY='sk_platform',
        PAYMONGO_WEBHOOK_SECRET='wh_platform',
        PAYMONGO_PLATFORM_MERCHANT_ID='org_parent',
    )
    def test_payments_ready_when_child_activated(self):
        PaymentIntegration.objects.create(
            company=self.company,
            account=self.account,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
            paymongo_account_id='org_child_1',
            activation_status='activated',
        )
        self.assertTrue(paymongo_configured(self.company.pk))
        self.assertTrue(company_can_accept_paymongo_payments(self.company.pk))
        ctx = get_paymongo_company_context(self.company.pk)
        assert ctx is not None
        self.assertEqual(ctx.child_account_id, 'org_child_1')
        self.assertEqual(ctx.platform_merchant_id, 'org_parent')
        self.assertEqual(ctx.platform_fee_bps, 100)

    @override_settings(
        PAYMONGO_SECRET_KEY='sk_platform',
        PAYMONGO_PLATFORM_MERCHANT_ID='org_parent',
    )
    def test_not_ready_without_child_account(self):
        self.assertTrue(paymongo_configured(self.company.pk))
        self.assertFalse(company_can_accept_paymongo_payments(self.company.pk))


class CompanyPayMongoIntegrationApiTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(name='Tenant', country=country)
        self.company = Company.objects.create(
            account=self.account,
            name='Pay Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.other_account = Account.objects.create(name='Other', country=country)
        self.other_company = Company.objects.create(
            account=self.other_account,
            name='Other Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.user = User.objects.create_user(
            username='user@test.com',
            email='user@test.com',
            password='test-pass',
            account=self.account,
            company=self.company,
        )

    @override_settings(PAYMONGO_SECRET_KEY='sk_platform')
    def test_get_shows_not_connected(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get(
            f'/api/companies/{self.company.pk}/payment-integrations/paymongo/',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['activation_status'], 'not_started')
        self.assertFalse(res.data['payments_ready'])

    def test_cannot_access_other_account_company(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get(
            f'/api/companies/{self.other_company.pk}/payment-integrations/paymongo/',
        )
        self.assertEqual(res.status_code, 404)

    @override_settings(
        PAYMONGO_SECRET_KEY='sk_platform',
        PAYMONGO_PLATFORM_MERCHANT_ID='org_parent',
    )
    def test_disconnect_clears_stored_child_account(self):
        from payments.paymongo_onboarding import disconnect_paymongo_integration

        integration = PaymentIntegration.all_objects.create(
            company=self.company,
            account=self.account,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
            paymongo_account_id='org_stale_test',
            activation_status='activated',
            identity_verification_status='passed',
        )
        disconnect_paymongo_integration(self.company.pk)
        integration.refresh_from_db()
        self.assertIsNotNone(integration.deleted_at)
        self.assertEqual(integration.paymongo_account_id, '')
        self.assertEqual(integration.activation_status, 'not_started')

    @override_settings(
        PAYMONGO_SECRET_KEY='sk_platform',
        PAYMONGO_PLATFORM_MERCHANT_ID='org_parent',
    )
    def test_onboarding_replaces_stale_child_on_404(self):
        from unittest.mock import patch

        from payments.paymongo_onboarding import start_paymongo_onboarding

        PaymentIntegration.all_objects.create(
            company=self.company,
            account=self.account,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
            paymongo_account_id='org_stale_test',
            activation_status='activated',
            identity_verification_status='passed',
        )
        new_account = {
            'id': 'org_live_new',
            'activation_status': 'pending',
            'person': {'identity_verification_status': 'pending'},
        }

        with patch(
            'payments.paymongo_onboarding.get_child_account',
            side_effect=__import__(
                'bookings.paymongo_client', fromlist=['PayMongoError']
            ).PayMongoError('Account not found', status_code=404),
        ), patch(
            'payments.paymongo_onboarding.create_child_merchant_account',
            return_value=new_account,
        ), patch(
            'payments.paymongo_onboarding.create_identity_verification_session',
            return_value={'url': 'https://verify.example/kyc'},
        ), patch(
            'payments.paymongo_onboarding.activate_child_account',
        ) as mock_activate:
            result = start_paymongo_onboarding(self.company)

        self.assertEqual(result.paymongo_account_id, 'org_live_new')
        mock_activate.assert_not_called()
