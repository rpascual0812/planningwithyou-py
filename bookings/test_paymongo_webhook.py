from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from bookings.models import (
    BookingItem,
    BookingPayment,
    BookingPaymentLink,
    BookingStatus,
)
from bookings.paymongo_webhook import (
    _extract_payment_from_event,
    _record_booking_payment,
    handle_paymongo_webhook_event,
)
from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account


def _payment_paid_event(payment_id: str, status: str, metadata: dict) -> dict:
    return {
        'type': 'payment.paid',
        'data': {
            'id': 'evt_test',
            'attributes': {
                'type': 'payment.paid',
                'data': {
                    'id': payment_id,
                    'type': 'payment',
                    'attributes': {
                        'status': status,
                        'amount': 150000,
                        'currency': 'PHP',
                        'metadata': metadata,
                        'payment_method_type': 'gcash',
                    },
                },
            },
        },
    }


class PayMongoWebhookPaymentRecordTests(TestCase):
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
            name='Main',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.status = BookingStatus.objects.create(account=self.account, title='New')
        self.booking = BookingItem.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0200',
            title='Event',
            total_amount=Decimal('1500.00'),
            required_downpayment_amount=Decimal('500.00'),
        )
        self.link = BookingPaymentLink.objects.create(
            booking=self.booking,
            account_id=self.account.id,
            company_id=self.company.id,
            public_token='11111111-2222-3333-4444-555555555555',
            base_amount=Decimal('500.00'),
            platform_fee=Decimal('5.00'),
            processing_fee_estimate=Decimal('20.00'),
            charge_amount=Decimal('525.00'),
            currency='PHP',
            status=BookingPaymentLink.Status.PENDING,
            expires_at=timezone.now() + timedelta(days=7),
            paymongo_checkout_session_id='cs_test_123',
        )

    def test_extract_payment_id_and_status(self):
        info = _extract_payment_from_event(
            _payment_paid_event(
                'pay_abc123',
                'paid',
                {'booking_payment_link_id': str(self.link.pk)},
            ),
        )
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info['payment_id'], 'pay_abc123')
        self.assertEqual(info['status'], 'paid')
        self.assertEqual(info['amount'], Decimal('1500.00'))

    def test_handle_webhook_records_failed_payment(self):
        handled = handle_paymongo_webhook_event(
            _payment_paid_event(
                'pay_failed_1',
                'failed',
                {'booking_payment_link_id': str(self.link.pk)},
            ),
        )
        self.assertTrue(handled)
        payment = BookingPayment.objects.get(transaction_id='pay_failed_1')
        self.assertEqual(payment.transaction_status, 'failed')
        self.assertEqual(payment.amount, Decimal('1500.00'))
        self.link.refresh_from_db()
        self.assertEqual(self.link.status, BookingPaymentLink.Status.PENDING)

    def test_handle_webhook_records_paid_and_marks_link(self):
        handled = handle_paymongo_webhook_event(
            _payment_paid_event(
                'pay_ok_1',
                'paid',
                {'booking_payment_link_id': str(self.link.pk)},
            ),
        )
        self.assertTrue(handled)
        payment = BookingPayment.objects.get(transaction_id='pay_ok_1')
        self.assertEqual(payment.transaction_status, 'paid')
        self.link.refresh_from_db()
        self.assertEqual(self.link.status, BookingPaymentLink.Status.PAID)
        self.assertIsNotNone(self.link.paid_at)

    def test_record_upserts_same_payment_id(self):
        _record_booking_payment(
            self.link,
            transaction_id='pay_dup',
            transaction_status='processing',
            payment_method='card',
            amount=Decimal('100.00'),
            api_response={'first': True},
        )
        _record_booking_payment(
            self.link,
            transaction_id='pay_dup',
            transaction_status='paid',
            payment_method='card',
            amount=Decimal('100.00'),
            api_response={'second': True},
        )
        self.assertEqual(
            BookingPayment.objects.filter(transaction_id='pay_dup').count(),
            1,
        )
        payment = BookingPayment.objects.get(transaction_id='pay_dup')
        self.assertEqual(payment.transaction_status, 'paid')
