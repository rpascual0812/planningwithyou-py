from django.test import SimpleTestCase, override_settings

from payments.paymongo_config import build_paymongo_onboarding_url


class BuildPaymongoOnboardingUrlTests(SimpleTestCase):
    @override_settings(
        PAYMONGO_ONBOARDING_URL='https://onboarding.paymongo.com/onboarding/merchants',
    )
    def test_appends_merchant_id_to_base(self):
        self.assertEqual(
            build_paymongo_onboarding_url('org_abc123'),
            'https://onboarding.paymongo.com/onboarding/merchants/org_abc123',
        )

    @override_settings(
        PAYMONGO_ONBOARDING_URL=(
            'https://onboarding.paymongo.com/onboarding/merchants/{merchant_id}'
        ),
    )
    def test_template_placeholder(self):
        self.assertEqual(
            build_paymongo_onboarding_url('org_xyz'),
            'https://onboarding.paymongo.com/onboarding/merchants/org_xyz',
        )
