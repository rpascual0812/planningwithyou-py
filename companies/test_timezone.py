import json
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from bookings.models import Quotation, QuotationStatus
from companies.middleware import (
    MUTATING_METHODS,
    CompanyTimezoneMiddleware,
    request_company_id,
)
from companies.models import Company
from companies.timezone import (
    activate_timezone_for_instance,
    normalize_company_timezone_name,
    zoneinfo_for_company_id,
)
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class CompanyTimezoneUtilsTests(TestCase):
    def test_normalize_missing_or_invalid_defaults_to_utc(self):
        self.assertEqual(normalize_company_timezone_name(''), 'UTC')
        self.assertEqual(normalize_company_timezone_name(None), 'UTC')
        self.assertEqual(normalize_company_timezone_name('Not/A/Zone'), 'UTC')

    def test_normalize_valid_zone(self):
        self.assertEqual(normalize_company_timezone_name('Asia/Manila'), 'Asia/Manila')

    def test_zoneinfo_for_company_id_uses_stored_timezone(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        supplier_type = SupplierType.objects.create(name='General')
        account = Account.objects.create(name='Tenant', country=country)
        company = Company.objects.create(
            account=account,
            name='Main',
            supplier_type=supplier_type,
            timezone='Asia/Manila',
        )
        tz = zoneinfo_for_company_id(company.pk)
        self.assertEqual(str(tz), 'Asia/Manila')

    def test_zoneinfo_for_company_id_without_company_is_utc(self):
        self.assertEqual(zoneinfo_for_company_id(None), ZoneInfo('UTC'))
        self.assertEqual(zoneinfo_for_company_id(999999), ZoneInfo('UTC'))


class CompanyTimezoneMiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='UTC',
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
            username='tzuser',
            email='tz@example.com',
            password='secret',
            account=cls.account,
            company=cls.company,
        )

    def test_mutating_methods_constant(self):
        self.assertEqual(MUTATING_METHODS, frozenset({'POST', 'PUT', 'PATCH', 'DELETE'}))

    def test_request_company_id_for_authenticated_user(self):
        request = RequestFactory().get('/api/bookings/')
        request.user = self.user
        self.assertEqual(request_company_id(request), self.company.pk)

    def test_request_company_id_from_json_body_on_post(self):
        request = RequestFactory().post(
            '/api/bookings/',
            data=json.dumps({'company_id': self.company.pk, 'title': 'Test'}),
            content_type='application/json',
        )
        request.user = self.user
        self.assertEqual(request_company_id(request), self.company.pk)

    def test_get_requests_activate_company_timezone(self):
        request = RequestFactory().get('/api/bookings/')
        request.user = self.user
        captured = {}

        def get_response(req):
            captured['tz'] = timezone.get_current_timezone_name()
            return None

        CompanyTimezoneMiddleware(get_response)(request)
        self.assertEqual(captured['tz'], 'Asia/Manila')
        self.assertEqual(timezone.get_current_timezone_name(), 'UTC')

    def test_post_activates_company_timezone(self):
        request = RequestFactory().post('/api/bookings/')
        request.user = self.user
        captured = {}

        def get_response(req):
            captured['tz'] = timezone.get_current_timezone_name()
            return None

        CompanyTimezoneMiddleware(get_response)(request)
        self.assertEqual(captured['tz'], 'Asia/Manila')
        self.assertEqual(timezone.get_current_timezone_name(), 'UTC')

    def test_all_mutating_methods_activate_company_timezone(self):
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            with self.subTest(method=method):
                request = getattr(RequestFactory(), method.lower())('/api/bookings/1/')
                request.user = self.user
                captured = {}

                def get_response(req):
                    captured['tz'] = timezone.get_current_timezone_name()
                    return None

                CompanyTimezoneMiddleware(get_response)(request)
                self.assertEqual(captured['tz'], 'Asia/Manila')

    def test_middleware_uses_utc_for_invalid_company_timezone(self):
        self.company.timezone = 'Invalid/Zone'
        self.company.save(update_fields=['timezone'])
        request = RequestFactory().post('/api/bookings/')
        request.user = self.user
        captured = {}

        def get_response(req):
            captured['tz'] = timezone.get_current_timezone_name()
            return None

        CompanyTimezoneMiddleware(get_response)(request)
        self.assertEqual(captured['tz'], 'UTC')


class CompanyTimezoneSaveSignalTests(TestCase):
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
        cls.status = QuotationStatus.objects.create(
            account=cls.account,
            company=cls.company,
            title='New',
        )

    def test_pre_save_activates_instance_company_timezone(self):
        booking = Quotation(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='ABC1234',
            title='Event',
        )
        with timezone.override(ZoneInfo('UTC')):
            activate_timezone_for_instance(booking)
            self.assertEqual(timezone.get_current_timezone_name(), 'Asia/Manila')

    def test_created_at_reflects_company_timezone_on_insert(self):
        manila = ZoneInfo('Asia/Manila')
        utc_now = datetime(2025, 6, 15, 6, 30, 0, tzinfo=ZoneInfo('UTC'))
        with patch('django.utils.timezone.now', return_value=utc_now):
            with timezone.override(ZoneInfo('UTC')):
                booking = Quotation.objects.create(
                    account=self.account,
                    company=self.company,
                    status=self.status,
                    unique_id='TZ12345',
                    title='Timezone event',
                )
        booking.refresh_from_db()
        self.assertEqual(booking.created_at.astimezone(manila), utc_now.astimezone(manila))


class CompanyTimezoneDrfTests(TestCase):
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
        cls.status = QuotationStatus.objects.create(
            account=cls.account,
            company=cls.company,
            title='New',
        )

    def test_booking_serializer_created_at_uses_company_timezone(self):
        from bookings.serializers import QuotationSerializer

        manila = ZoneInfo('Asia/Manila')
        utc = datetime(2025, 6, 15, 1, 0, 0, tzinfo=ZoneInfo('UTC'))
        booking = Quotation.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='DRF1234',
            title='Event',
            created_at=utc.astimezone(manila),
        )
        data = QuotationSerializer(booking).data
        self.assertTrue(str(data['created_at']).startswith('2025-06-15T09:00:00'))
