from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from payments.paymongo_platform_client import build_transfer_config
from payments.xendit_split_rules import (
    SETTING_KEY,
    get_platform_fee_split_rule_id,
    platform_fee_percent,
)
from subscriptions.xendit_client import XenditError
from system_settings.models import SystemSetting


class BuildTransferConfigTests(SimpleTestCase):
    def test_one_percent_to_platform_remainder_to_child(self):
        config = build_transfer_config(
            child_account_id='child_acc_1',
            platform_merchant_id='platform_merchant_1',
            platform_fee_bps=100,
        )
        self.assertEqual(config['transfer_to'], 'child_acc_1')
        self.assertEqual(len(config['recipients']), 1)
        recipient = config['recipients'][0]
        self.assertEqual(recipient['merchant_id'], 'platform_merchant_1')
        self.assertEqual(recipient['split_type'], 'percentage_net')
        self.assertEqual(recipient['value'], 100)


@override_settings(
    XENDIT_SECRET_KEY='sk_test',
    XENDIT_PLATFORM_FEE_PERCENT='1',
    XENDIT_PLATFORM_SPLIT_RULE_ID='',
    XENDIT_PLATFORM_MASTER_ACCOUNT_ID='master_bid_123',
)
class XenditSplitRulesTests(TestCase):
    def test_platform_fee_percent_defaults_to_one(self):
        self.assertEqual(platform_fee_percent(), 1.0)

    @override_settings(XENDIT_PLATFORM_SPLIT_RULE_ID='sr_explicit')
    def test_explicit_split_rule_id_from_settings(self):
        self.assertEqual(get_platform_fee_split_rule_id(), 'sr_explicit')

    @patch('payments.xendit_split_rules._request')
    def test_creates_and_stores_split_rule_when_missing(self, mock_request):
        mock_request.return_value = {'id': 'sr_new_1'}
        rule_id = get_platform_fee_split_rule_id()
        self.assertEqual(rule_id, 'sr_new_1')
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], 'POST')
        self.assertEqual(call_args[0][1], '/split_rules')
        routes = call_args[0][2]['routes']
        self.assertEqual(routes[0]['percent_amount'], 1.0)
        self.assertEqual(routes[0]['destination_account_id'], 'master_bid_123')
        self.assertEqual(call_args[0][2]['description'], 'Platform fee on quotation payment links')
        row = SystemSetting.objects.get(name=SETTING_KEY)
        self.assertEqual(row.value, 'sr_new_1')

    @override_settings(XENDIT_PLATFORM_SPLIT_RULE_ID='sr_cached')
    def test_reuses_stored_split_rule_without_api_call(self):
        SystemSetting.objects.create(name=SETTING_KEY, value='sr_cached')
        with patch('payments.xendit_split_rules._request') as mock_request:
            self.assertEqual(get_platform_fee_split_rule_id(), 'sr_cached')
            mock_request.assert_not_called()

    @override_settings(XENDIT_PLATFORM_FEE_PERCENT='0')
    def test_zero_percent_skips_split_rule(self):
        self.assertEqual(get_platform_fee_split_rule_id(), '')

    @override_settings(XENDIT_PLATFORM_MASTER_ACCOUNT_ID='')
    def test_missing_master_account_id_raises_clear_error(self):
        with self.assertRaises(XenditError) as ctx:
            get_platform_fee_split_rule_id()
        self.assertIn('XENDIT_PLATFORM_MASTER_ACCOUNT_ID', str(ctx.exception))


@override_settings(XENDIT_SECRET_KEY='sk_test', XENDIT_PLATFORM_SPLIT_RULE_ID='sr_link')
class CreateQuotationPaymentSessionTests(SimpleTestCase):
    @patch('bookings.xendit_payment_links._request')
    @patch('bookings.xendit_payment_links.get_platform_fee_split_rule_id', return_value='sr_link')
    def test_session_request_includes_split_rule_header(self, _mock_rule, mock_request):
        mock_request.return_value = {
            'payment_link_url': 'https://checkout.xendit.co/web/paylink_1',
        }
        from bookings.xendit_payment_links import create_quotation_payment_session

        create_quotation_payment_session(
            sub_account_id='sub_abc',
            reference_id='quote-link-token',
            description='Payment for booking',
            amount_php=Decimal('1010.00'),
            success_url='https://app/success',
            cancel_url='https://app/cancel',
            metadata={'kind': 'quotation_payment_link'},
            customer_email='buyer@example.com',
        )
        mock_request.assert_called_once()
        kwargs = mock_request.call_args.kwargs
        self.assertEqual(kwargs['for_user_id'], 'sub_abc')
        self.assertEqual(kwargs['with_split_rule'], 'sr_link')
