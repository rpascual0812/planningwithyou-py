from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from payments.paymongo_platform_client import create_child_merchant


@override_settings(
    PAYMONGO_SECRET_KEY='sk_test',
    PAYMONGO_MERCHANT_CHILDREN_URL='https://api.paymongo.com/v1/merchants/children',
)
class CreateChildMerchantTests(SimpleTestCase):
    @patch('payments.paymongo_platform_client._platform_request')
    def test_posts_merchants_children_payload(self, mock_request):
        mock_request.return_value = {
            'data': {'id': 'org_child_abc', 'type': 'merchant'},
        }
        create_child_merchant(
            trade_name='ABC Events',
            business_type='sole_proprietor',
            email='owner@abcevents.com',
            phone_number='+639171234567',
        )
        mock_request.assert_called_once()
        method, path, body = mock_request.call_args[0]
        self.assertEqual(method, 'POST')
        self.assertEqual(path, '/v1/merchants/children')
        attrs = body['data']['attributes']
        self.assertTrue(attrs['accepted_terms_and_conditions'])
        self.assertEqual(attrs['features'], ['payment_gateway'])
        self.assertEqual(attrs['business']['trade_name'], 'ABC Events')
        self.assertEqual(attrs['business']['type'], 'sole_proprietor')
        self.assertEqual(attrs['business']['email'], 'owner@abcevents.com')
        self.assertEqual(attrs['business']['phone_number'], '+639171234567')
