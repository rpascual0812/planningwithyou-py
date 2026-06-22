from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import (
    Quotation,
    QuotationPayment,
    QuotationPaymentLink,
    QuotationStatus,
)
from bookings.payment_link_confirm import confirm_quotation_payment_link
from companies.models import Company
from contacts.models import Contact
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account, User
from users.registration import seed_company_defaults


class PaymentLinkConfirmTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence('accounts','id'), "
                "COALESCE((SELECT MAX(id) FROM accounts), 1))"
            )
        country = Country.objects.create(
            name='Testland Confirm',
            iso_code='TX9',
            iso2_code='Z9',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='Planner')
        cls.account = Account.objects.create(name='Tenant', country=country)
        cls.company = Company.objects.create(
            account=cls.account,
            name='Acme Events Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        seed_company_defaults(cls.account, cls.company)
        cls.status = QuotationStatus.objects.create(
            account=cls.account,
            company=cls.company,
            title='New',
        )
        cls.user = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='test-pass',
            account=cls.account,
            company=cls.company,
        )
        cls.contact = Contact.objects.create(
            account=cls.account,
            company_org=cls.company,
            first_name='Jane',
            last_name='Client',
            email='jane.client@example.com',
        )
        cls.booking = Quotation.objects.create(
            account=cls.account,
            company=cls.company,
            status=cls.status,
            contact=cls.contact,
            unique_id='26-0500',
            title='Wedding Reception',
            total_amount=Decimal('1500.00'),
            required_downpayment_amount=Decimal('500.00'),
            created_by=cls.user,
        )

    def _create_xendit_link(self) -> QuotationPaymentLink:
        token = uuid4()
        return QuotationPaymentLink.objects.create(
            quotation=self.booking,
            account_id=self.account.id,
            company_id=self.company.id,
            public_token=token,
            base_amount=Decimal('500.00'),
            platform_fee=Decimal('5.00'),
            processing_fee_estimate=Decimal('20.00'),
            charge_amount=Decimal('525.00'),
            currency='PHP',
            status=QuotationPaymentLink.Status.PENDING,
            expires_at=timezone.now() + timedelta(days=7),
            payment_provider=QuotationPaymentLink.PaymentProvider.XENDIT,
            xendit_payment_session_id=f'ps-confirm-{token.hex[:8]}',
        )

    @patch('bookings.payment_link_confirm.apply_xendit_booking_payment_session_completed')
    @patch('bookings.payment_link_confirm.retrieve_session')
    def test_confirm_records_xendit_payment_on_success_return(
        self,
        mock_retrieve_session,
        mock_apply_completed,
    ):
        link = self._create_xendit_link()
        session = {
            'payment_session_id': link.xendit_payment_session_id,
            'reference_id': f'quote-link-{link.public_token}',
            'status': 'COMPLETED',
            'payment_id': 'py-confirm-1',
        }
        mock_retrieve_session.return_value = session

        def _apply(session_payload):
            from bookings.paymongo_webhook import _record_booking_payment

            breakdown = {
                'charge_amount': link.charge_amount,
                'base_amount': link.base_amount,
                'platform_fee': link.platform_fee,
                'processing_fee': link.processing_fee_estimate,
                'net_amount': Decimal('500.00'),
            }
            _record_booking_payment(
                link,
                transaction_id='py-confirm-1',
                transaction_status='paid',
                payment_method='xendit',
                breakdown=breakdown,
                api_response=session_payload,
            )
            return True

        mock_apply_completed.side_effect = _apply

        result = confirm_quotation_payment_link(link)
        self.assertTrue(result['confirmed'])
        self.assertFalse(result['pending'])
        self.assertFalse(result['already_recorded'])
        self.assertEqual(result['payment_link']['status'], 'paid')
        link.refresh_from_db()
        self.assertIsNotNone(link.success_return_confirmed_at)
        self.assertTrue(
            QuotationPayment.objects.filter(transaction_id='py-confirm-1').exists(),
        )

    def test_confirm_already_paid_marks_first_success_return(self):
        link = self._create_xendit_link()
        link.status = QuotationPaymentLink.Status.PAID
        link.paid_at = timezone.now()
        link.save(update_fields=['status', 'paid_at', 'updated_at'])

        result = confirm_quotation_payment_link(link)
        self.assertTrue(result['confirmed'])
        self.assertFalse(result['already_recorded'])
        link.refresh_from_db()
        self.assertIsNotNone(link.success_return_confirmed_at)

    def test_confirm_second_success_return_is_already_recorded(self):
        link = self._create_xendit_link()
        link.status = QuotationPaymentLink.Status.PAID
        link.paid_at = timezone.now()
        link.success_return_confirmed_at = timezone.now()
        link.save(
            update_fields=[
                'status',
                'paid_at',
                'success_return_confirmed_at',
                'updated_at',
            ],
        )

        with patch('bookings.payment_link_confirm.retrieve_session') as mock_retrieve:
            result = confirm_quotation_payment_link(link)
            mock_retrieve.assert_not_called()

        self.assertTrue(result['confirmed'])
        self.assertTrue(result['already_recorded'])

    def test_confirm_endpoint_requires_success_status(self):
        link = self._create_xendit_link()
        response = self.client.post(
            reverse('public-payment-link-confirm', kwargs={'token': str(link.public_token)}),
        )
        self.assertEqual(response.status_code, 400)

    @patch('bookings.payment_link_confirm.apply_xendit_booking_payment_session_completed', return_value=False)
    @patch('bookings.payment_link_confirm.retrieve_session')
    def test_confirm_endpoint_returns_pending_when_provider_not_ready(
        self,
        mock_retrieve_session,
        _mock_apply,
    ):
        link = self._create_xendit_link()
        mock_retrieve_session.return_value = {
            'payment_session_id': link.xendit_payment_session_id,
            'status': 'ACTIVE',
        }
        response = self.client.post(
            reverse(
                'public-payment-link-confirm',
                kwargs={'token': str(link.public_token)},
            )
            + '?status=success',
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body['confirmed'])
        self.assertTrue(body['pending'])
        self.assertFalse(body['already_recorded'])
