from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from bookings.models import (
    QuotationGroup,
    Quotation,
    QuotationLine,
    QuotationPayment,
    QuotationStatus,
)
from companies.models import Company
from countries.models import Country
from subscriptions.models import AccountSubscription, Subscription
from suppliers.models import SupplierType
from users.models import Account
from users.roles import ensure_owner_role
from ai_assistant.access import account_has_ai_assistant_plan, ai_assistant_plans

User = get_user_model()


def _sync_account_id_sequence() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence('accounts', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM accounts))"
        )


class QuotationDuplicateAndAiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _sync_account_id_sequence()
        cls.country = Country.objects.create(
            name='AI Dup Testland',
            iso_code='ADT',
            iso2_code='Q1',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        cls.supplier_type = SupplierType.objects.create(name='General')
        cls.pro_plan = Subscription.objects.filter(plan='pro', billing_cycle='monthly').first()
        if cls.pro_plan is None:
            cls.pro_plan = Subscription.objects.create(
                plan='pro',
                name='Pro',
                billing_cycle='monthly',
                base_price=Decimal('995.00'),
                is_active=True,
            )
        cls.ai_plan = Subscription.objects.filter(plan='ai', billing_cycle='monthly').first()
        if cls.ai_plan is None:
            cls.ai_plan = Subscription.objects.create(
                plan='ai',
                name='AI Plus',
                billing_cycle='monthly',
                base_price=Decimal('1995.00'),
                is_active=True,
            )
        cls.account = Account.objects.create(
            name='Tenant',
            country=cls.country,
            is_active=True,
        )
        cls.company = Company.objects.create(
            account=cls.account,
            name='Main Co',
            supplier_type=cls.supplier_type,
            is_main=True,
            is_active=True,
        )
        cls.status = QuotationStatus.objects.create(
            account=cls.account,
            company=cls.company,
            title='New',
        )
        cls.user = User.objects.create_user(
            username='planner@test.example',
            email='planner@test.example',
            password='secret12',
            account=cls.account,
            company=cls.company,
            is_verified=True,
            role=ensure_owner_role(cls.account),
        )
        AccountSubscription.objects.create(
            account=cls.account,
            subscription=cls.pro_plan,
            status=AccountSubscription.Status.ACTIVE,
            team_seats=1,
            start_date=timezone.localdate(),
            end_date=None,
            base_price=cls.pro_plan.base_price,
            total_per_users=Decimal('0'),
            total_price=cls.pro_plan.base_price,
        )
        cls.source = Quotation.objects.create(
            account=cls.account,
            company=cls.company,
            status=cls.status,
            unique_id='26-0100',
            title='Wedding Package',
            total_amount=Decimal('50000.00'),
            required_downpayment_amount=Decimal('10000.00'),
            notes='Garden venue',
        )
        group = QuotationGroup.objects.create(
            quotation=cls.source,
            name='Services',
        )
        QuotationLine.objects.create(
            account=cls.account,
            quotation=cls.source,
            quotation_group=group,
            label='Venue',
            field_type='text',
            value='Garden',
            price=Decimal('30000.00'),
            sort_order=0,
        )
        QuotationPayment.objects.create(
            account=cls.account,
            quotation=cls.source,
            company=cls.company,
            base_amount=Decimal('5000.00'),
            charge_amount=Decimal('5000.00'),
            transaction_status='paid',
            transaction_date=timezone.now(),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _set_account_plan(self, plan_slug: str) -> None:
        plan = self.ai_plan if plan_slug == 'ai' else self.pro_plan
        row = AccountSubscription.objects.get(account=self.account)
        row.subscription = plan
        row.base_price = plan.base_price
        row.total_price = plan.base_price
        row.save(update_fields=['subscription', 'base_price', 'total_price'])

    @patch('bookings.duplicate.generate_booking_pdf_task.delay')
    def test_duplicate_creates_copy_without_payments(self, mock_pdf):
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(
                f'/quotation-items/{self.source.pk}/duplicate/',
                {},
                format='json',
            )
        self.assertEqual(res.status_code, 201, res.content)
        data = res.json()
        self.assertNotEqual(data['id'], self.source.pk)
        self.assertNotEqual(data['unique_id'], self.source.unique_id)
        self.assertEqual(data['title'], 'Copy of Wedding Package')
        self.assertEqual(len(data['field_values']), 1)
        self.assertEqual(QuotationPayment.objects.filter(quotation_id=data['id']).count(), 0)
        mock_pdf.assert_called_once()

    @patch('bookings.duplicate.generate_booking_pdf_task.delay')
    def test_duplicate_custom_title(self, mock_pdf):
        res = self.client.post(
            f'/quotation-items/{self.source.pk}/duplicate/',
            {'title': 'Spring Wedding Copy'},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['title'], 'Spring Wedding Copy')

    @override_settings(OPENAI_API_KEY='')
    def test_summarize_requires_configuration(self):
        self._set_account_plan('ai')
        res = self.client.post(
            f'/ai/quotations/{self.source.pk}/summarize/',
            {},
            format='json',
        )
        self.assertEqual(res.status_code, 503)

    @override_settings(OPENAI_API_KEY='test-key', AI_ASSISTANT_PLANS='ai')
    def test_pro_plan_not_eligible_for_ai(self):
        self.assertNotIn('pro', ai_assistant_plans())
        self.assertFalse(account_has_ai_assistant_plan(self.account.pk))

        res = self.client.post(
            f'/ai/quotations/{self.source.pk}/summarize/',
            {},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    @override_settings(OPENAI_API_KEY='test-key', AI_ASSISTANT_PLANS='ai')
    def test_ai_plus_plan_eligible(self):
        self._set_account_plan('ai')
        self.assertTrue(account_has_ai_assistant_plan(self.account.pk))

    @override_settings(OPENAI_API_KEY='test-key', AI_ASSISTANT_PLANS='ai')
    @patch('ai_assistant.services.complete_json')
    def test_summarize_and_draft_email(self, mock_complete):
        self._set_account_plan('ai')
        mock_complete.return_value = (
            {'summary': 'A wedding quote.', 'highlights': ['Total 50000']},
            {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30},
        )
        res = self.client.post(
            f'/ai/quotations/{self.source.pk}/summarize/',
            {'prompt': 'Keep it brief'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['summary'], 'A wedding quote.')

        mock_complete.return_value = (
            {
                'subject': 'Your quotation',
                'body_html': '<p>Hello</p>',
            },
            {'prompt_tokens': 12, 'completion_tokens': 18, 'total_tokens': 30},
        )
        draft_res = self.client.post(
            f'/ai/quotations/{self.source.pk}/draft-email/',
            {},
            format='json',
        )
        self.assertEqual(draft_res.status_code, 200)
        self.assertEqual(draft_res.json()['subject'], 'Your quotation')

    @override_settings(OPENAI_API_KEY='test-key', AI_ASSISTANT_PLANS='ai')
    def test_status_endpoint(self):
        self._set_account_plan('ai')
        res = self.client.get('/ai/assistant/status/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['configured'])
        self.assertTrue(res.json()['plan_eligible'])
        self.assertTrue(res.json()['available'])
