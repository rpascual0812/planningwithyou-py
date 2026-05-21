from decimal import Decimal

from django.test import SimpleTestCase

from bookings.payment_pricing import (
    PAYMONGO_FIXED_FEE_PHP,
    PAYMONGO_WORST_MDR_RATE,
    PLATFORM_FEE_RATE_ON_BASE,
    amount_to_centavos,
    compute_payment_link_pricing,
)


class PaymentLinkPricingTests(SimpleTestCase):
    def test_gross_up_base_10000(self):
        pricing = compute_payment_link_pricing(Decimal('10000'))
        self.assertEqual(pricing.base_amount, Decimal('10000.00'))
        self.assertEqual(pricing.platform_fee, Decimal('100.00'))
        charge = pricing.charge_amount
        paymongo = charge * PAYMONGO_WORST_MDR_RATE + PAYMONGO_FIXED_FEE_PHP
        net = charge - paymongo - pricing.platform_fee
        self.assertGreaterEqual(net, pricing.base_amount)
        self.assertEqual(amount_to_centavos(charge), int(charge * 100))

    def test_platform_fee_is_one_percent_of_base(self):
        pricing = compute_payment_link_pricing(Decimal('5000'))
        self.assertEqual(
            pricing.platform_fee,
            (Decimal('5000') * PLATFORM_FEE_RATE_ON_BASE).quantize(Decimal('0.01')),
        )

    def test_rejects_zero_base(self):
        with self.assertRaises(ValueError):
            compute_payment_link_pricing(Decimal('0'))
