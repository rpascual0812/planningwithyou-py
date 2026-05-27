from django.test import SimpleTestCase

from payments.paymongo_platform_client import extract_hosted_url


class ExtractHostedUrlTests(SimpleTestCase):
    def test_v1_onboarding_link_attributes(self):
        resource = {
            'id': 'onb_1',
            'attributes': {
                'checkout_url': 'https://paymongo.com/onboarding/abc',
            },
        }
        self.assertEqual(
            extract_hosted_url(resource),
            'https://paymongo.com/onboarding/abc',
        )

    def test_v2_identity_session_top_level_url(self):
        resource = {
            'id': 'ivs_1',
            'url': 'https://verify.paymongo.com/session/xyz',
        }
        self.assertEqual(
            extract_hosted_url(resource),
            'https://verify.paymongo.com/session/xyz',
        )

    def test_v2_account_onboarding_url(self):
        resource = {
            'id': 'org_1',
            'onboarding_url': 'https://seeds-onboarding.paymongo.com/onboarding/merchants/org_1',
        }
        self.assertIn('seeds-onboarding', extract_hosted_url(resource))

    def test_redirect_nested_checkout_url(self):
        resource = {
            'attributes': {
                'redirect': {
                    'checkout_url': 'https://test-sources.paymongo.com/sources?id=src_1',
                },
            },
        }
        self.assertIn('test-sources', extract_hosted_url(resource))
