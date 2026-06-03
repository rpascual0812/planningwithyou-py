"""Gross-up pricing for public PayMongo checkout (platform account)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

# Worst-case standard MDR so the company still receives the full quote when the
# customer picks any PayMongo method (international card: 4.02% + ₱13.39).
PAYMONGO_WORST_MDR_RATE = Decimal('0.0402')
PAYMONGO_FIXED_FEE_PHP = Decimal('13.39')
PLATFORM_FEE_RATE_ON_BASE = Decimal('0.01')
TWOPLACES = Decimal('0.01')


@dataclass(frozen=True)
class PaymentLinkPricing:
    base_amount: Decimal
    platform_fee: Decimal
    processing_fee_estimate: Decimal
    charge_amount: Decimal

    @property
    def fees_total(self) -> Decimal:
        return self.platform_fee + self.processing_fee_estimate


def _quantize_php(amount: Decimal) -> Decimal:
    return amount.quantize(TWOPLACES, rounding=ROUND_CEILING)


def compute_payment_link_pricing(base_amount: Decimal) -> PaymentLinkPricing:
    """
    Customer pays ``charge_amount`` so that after PayMongo (worst-case) and our
    1% platform fee (on booking total), the company nets ``base_amount``.
    """
    base = _quantize_php(Decimal(base_amount))
    if base <= 0:
        raise ValueError('Quotation total must be greater than zero.')

    platform_fee = _quantize_php(base * PLATFORM_FEE_RATE_ON_BASE)
    numerator = base + platform_fee + PAYMONGO_FIXED_FEE_PHP
    denominator = Decimal('1') - PAYMONGO_WORST_MDR_RATE
    charge_amount = _quantize_php(numerator / denominator)
    paymongo_at_charge = _quantize_php(
        charge_amount * PAYMONGO_WORST_MDR_RATE + PAYMONGO_FIXED_FEE_PHP,
    )
    processing_fee_estimate = _quantize_php(
        charge_amount - base - platform_fee,
    )
    # Keep breakdown consistent when rounding shifts a centavo.
    if processing_fee_estimate < paymongo_at_charge:
        processing_fee_estimate = paymongo_at_charge

    return PaymentLinkPricing(
        base_amount=base,
        platform_fee=platform_fee,
        processing_fee_estimate=processing_fee_estimate,
        charge_amount=charge_amount,
    )


def amount_to_centavos(amount: Decimal) -> int:
    return int(_quantize_php(amount) * 100)
