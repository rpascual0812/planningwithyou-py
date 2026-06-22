from django.test import TestCase

from companies.models import CompanyKybVerification
from payments.xendit_merchant_onboarding import (
    _is_legacy_onboarding_url,
    _map_xendit_account_status,
)


class XenditMerchantOnboardingTests(TestCase):
    def test_map_live_status_to_approved(self):
        self.assertEqual(
            _map_xendit_account_status('LIVE'),
            CompanyKybVerification.XenditStatus.APPROVED,
        )

    def test_map_invited_status_to_pending(self):
        self.assertEqual(
            _map_xendit_account_status('INVITED'),
            CompanyKybVerification.XenditStatus.PENDING,
        )

    def test_legacy_onboarding_url_detection(self):
        self.assertTrue(
            _is_legacy_onboarding_url(
                'https://onboarding.xendit.com/onboarding/merchants/abc',
            ),
        )
        self.assertFalse(_is_legacy_onboarding_url('https://dashboard.xendit.co/'))
