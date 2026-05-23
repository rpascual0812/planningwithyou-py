from django.test import TestCase, override_settings

from companies.models import Company
from config.models import Country
from payments.models import PaymentIntegration
from payments.paymongo_config import get_paymongo_config, paymongo_configured
from suppliers.models import SupplierType
from users.models import Account, User


class PayMongoConfigTests(TestCase):
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

    @override_settings(PAYMONGO_SECRET_KEY='sk_platform', PAYMONGO_WEBHOOK_SECRET='wh_platform')
    def test_platform_defaults_when_no_integration(self):
        cfg = get_paymongo_config(self.company.pk)
        self.assertIsNotNone(cfg)
        assert cfg is not None
        self.assertTrue(cfg.uses_platform_defaults)
        self.assertEqual(cfg.secret_key, 'sk_platform')
        self.assertTrue(paymongo_configured(self.company.pk))

    @override_settings(PAYMONGO_SECRET_KEY='sk_platform', PAYMONGO_WEBHOOK_SECRET='wh_platform')
    def test_company_integration_overrides_platform(self):
        PaymentIntegration.objects.create(
            company=self.company,
            account=self.account,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
            key='sk_company',
            secret='wh_company',
        )
        cfg = get_paymongo_config(self.company.pk)
        assert cfg is not None
        self.assertFalse(cfg.uses_platform_defaults)
        self.assertEqual(cfg.secret_key, 'sk_company')
        self.assertEqual(cfg.webhook_secret, 'wh_company')


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

    def test_get_shows_platform_default(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get(
            f'/api/companies/{self.company.pk}/payment-integrations/paymongo/',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['uses_platform_defaults'])
        self.assertFalse(res.data['has_custom_credentials'])

    def test_put_saves_custom_credentials(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.put(
            f'/api/companies/{self.company.pk}/payment-integrations/paymongo/',
            {'key': 'sk_test_abc', 'secret': 'whsec_test'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['has_custom_credentials'])
        self.assertFalse(res.data['uses_platform_defaults'])
        integration = PaymentIntegration.objects.get(company=self.company)
        self.assertEqual(integration.key, 'sk_test_abc')

    def test_cannot_access_other_account_company(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get(
            f'/api/companies/{self.other_company.pk}/payment-integrations/paymongo/',
        )
        self.assertEqual(res.status_code, 404)
