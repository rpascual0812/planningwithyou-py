from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from bookings.models import Quotation, QuotationPayment, QuotationStatus, Tag
from config.models import Config
from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account, User


class DashboardSummaryTests(TestCase):
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
        self.main = Company.objects.create(
            account=self.account,
            name='Main Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.status = QuotationStatus.objects.create(
            account=self.account,
            company=self.main,
            title='Confirmed',
            color='#1f3a5f',
        )
        self.booking = Quotation.objects.create(
            account=self.account,
            company=self.main,
            status=self.status,
            unique_id='26-0200',
            title='Wedding',
            total_amount=Decimal('10000.00'),
            required_downpayment_amount=Decimal('2000.00'),
            date_of_event=timezone.now() + timedelta(days=3),
        )
        QuotationPayment.objects.create(
            quotation=self.booking,
            account=self.account,
            company=self.main,
            base_amount=Decimal('3000.00'),
            amount=Decimal('3000.00'),
            transaction_status='paid',
            transaction_id='pay_1',
        )
        self.user = User.objects.create_user(
            username='dash@test.com',
            email='dash@test.com',
            password='test-pass',
            account=self.account,
            company=self.main,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_summary_per_company(self):
        res = self.client.get('/dashboard/summary/')
        self.assertEqual(res.status_code, 200)
        main = res.data['companies'][0]
        self.assertEqual(main['name'], 'Main Co')
        self.assertEqual(main['bookings_owned']['count'], 1)
        self.assertEqual(main['payouts']['pending_count'], 1)

    def test_profit_progress_sums_bookings_by_status_tag(self):
        done_tag = Tag.objects.create(
            account=self.account,
            company=self.main,
            tag='done',
        )
        self.status.tags.add(done_tag)
        Config.objects.create(
            account=self.account,
            company=self.main,
            scope='profit_progress',
            name='tag',
            value=str(done_tag.pk),
        )
        res = self.client.get(
            f'/dashboard/profit-progress/?company_id={self.main.pk}',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['tag_id'], done_tag.pk)
        self.assertEqual(res.data['tag_ids'], [done_tag.pk])
        self.assertEqual(res.data['tag_name'], 'done')
        self.assertEqual(res.data['total_amount'], '10000.00')
        self.assertEqual(res.data['display_value'], '10.0K+')

    def test_profit_progress_sums_multiple_status_tags(self):
        done_tag = Tag.objects.create(
            account=self.account,
            company=self.main,
            tag='done',
        )
        active_tag = Tag.objects.create(
            account=self.account,
            company=self.main,
            tag='active',
        )
        other_status = QuotationStatus.objects.create(
            account=self.account,
            company=self.main,
            title='In progress',
            color='#336699',
        )
        other_status.tags.add(active_tag)
        self.status.tags.add(done_tag)
        Quotation.objects.create(
            account=self.account,
            company=self.main,
            status=other_status,
            unique_id='26-0201',
            title='Birthday',
            total_amount=Decimal('5000.00'),
            required_downpayment_amount=Decimal('1000.00'),
            date_of_event=timezone.now() + timedelta(days=5),
        )
        Config.objects.create(
            account=self.account,
            company=self.main,
            scope='profit_progress',
            name='tag',
            value=f'{done_tag.pk},{active_tag.pk}',
        )
        res = self.client.get(
            f'/dashboard/profit-progress/?company_id={self.main.pk}',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['tag_ids'], [done_tag.pk, active_tag.pk])
        self.assertEqual(res.data['tag_name'], 'done, active')
        self.assertEqual(res.data['total_amount'], '15000.00')

    def test_active_projects_counts_bookings_by_status_tag(self):
        done_tag = Tag.objects.create(
            account=self.account,
            company=self.main,
            tag='confirmed',
        )
        self.status.tags.add(done_tag)
        Config.objects.create(
            account=self.account,
            company=self.main,
            scope='active_projects',
            name='tag',
            value=str(done_tag.pk),
        )
        res = self.client.get(
            f'/dashboard/active-projects/?company_id={self.main.pk}',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['tag_id'], done_tag.pk)
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['display_value'], '1')
