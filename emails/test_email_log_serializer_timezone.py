from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from countries.models import Country
from emails.models import EmailLog
from emails.serializers import EmailLogSerializer
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class EmailLogSerializerTimezoneTests(TestCase):
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
            username='seremail',
            email='ser@example.com',
            password='secret',
            account=cls.account,
            company=cls.company,
        )

    def test_created_at_serialized_in_company_timezone(self):
        utc = datetime(2025, 6, 15, 1, 15, 0, tzinfo=ZoneInfo('UTC'))
        log = EmailLog.objects.create(
            account=self.account,
            company=self.company,
            to=['a@b.com'],
            email_from='from@example.com',
            subject='Hi',
            created_at=utc.astimezone(ZoneInfo('Asia/Manila')),
        )
        data = EmailLogSerializer(log).data
        self.assertEqual(data['company_timezone'], 'Asia/Manila')
        self.assertTrue(data['created_at'].startswith('2025-06-15T09:15:00'))
