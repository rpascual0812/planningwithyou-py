from decimal import Decimal

from django.test import TestCase

from bookings.models import QuotationPayment
from bookings.payment_receipts import payment_receipt_filename


class PaymentReceiptFilenameTests(TestCase):
    def test_filename_uses_transaction_id_and_payment_method(self):
        payment = QuotationPayment(
            pk=7,
            transaction_id='pay_abc123',
            payment_method='card',
        )
        self.assertEqual(payment_receipt_filename(payment), 'pay_abc123_card.pdf')

    def test_filename_sanitizes_unsafe_characters(self):
        payment = QuotationPayment(
            pk=8,
            transaction_id='pay/abc 123',
            payment_method='gcash wallet',
        )
        self.assertEqual(payment_receipt_filename(payment), 'pay-abc-123_gcash-wallet.pdf')

    def test_filename_falls_back_when_fields_missing(self):
        payment = QuotationPayment(pk=9, transaction_id='', payment_method='')
        self.assertEqual(payment_receipt_filename(payment), 'payment-9.pdf')

        payment.transaction_id = 'only-txn'
        self.assertEqual(payment_receipt_filename(payment), 'only-txn.pdf')
