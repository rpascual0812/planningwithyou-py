from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from companies.timezone import now_in_company_timezone
from countries.models import Country
from emails.mail import create_and_queue_email
from emails.models import EmailLog
from emails.timezone_helpers import email_log_company_id
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class EmailLogTimezoneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        supplier_type = SupplierType.objects.create(name='General')
        cls.account = Account.objects.create(name='Tenant', country=country)
        cls.company = Company.objects.create(
            account=cls.account,
            name='Main',
            supplier_type=supplier_type,
            timezone='Asia/Manila',
        )
        cls.user = User.objects.create_user(
            username='emailuser',
            email='email@example.com',
            password='secret',
            account=cls.account,
            company=cls.company,
        )

    def test_email_log_company_id_uses_company_fk(self):
        log = EmailLog(account=self.account, company=self.company, to=['a@b.com'])
        self.assertEqual(email_log_company_id(log), self.company.pk)

    def test_email_log_company_id_falls_back_to_creator(self):
        log = EmailLog(
            account=self.account,
            to=['a@b.com'],
            created_by=self.user,
        )
        self.assertEqual(email_log_company_id(log), self.company.pk)

    def test_now_in_company_timezone_converts_utc_now(self):
        manila = ZoneInfo('Asia/Manila')
        utc_now = datetime(2025, 6, 15, 1, 15, 0, tzinfo=ZoneInfo('UTC'))
        with patch('django.utils.timezone.now', return_value=utc_now):
            local = now_in_company_timezone(self.company.pk)
        self.assertEqual(local.tzinfo, manila)
        self.assertEqual(local, datetime(2025, 6, 15, 9, 15, 0, tzinfo=manila))

    def test_create_and_queue_email_created_at_uses_company_timezone(self):
        manila = ZoneInfo('Asia/Manila')
        utc_now = datetime(2025, 6, 15, 1, 15, 0, tzinfo=ZoneInfo('UTC'))
        with patch('django.utils.timezone.now', return_value=utc_now):
            with timezone.override(ZoneInfo('UTC')):
                log = create_and_queue_email(
                    to=['guest@example.com'],
                    subject='Hello',
                    body='<p>Hi</p>',
                    account=self.account,
                    company=self.company,
                    created_by=self.user,
                )
        log.refresh_from_db()
        self.assertEqual(log.created_at.astimezone(manila), utc_now.astimezone(manila))
