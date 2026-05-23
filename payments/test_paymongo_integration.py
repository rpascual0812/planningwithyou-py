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
