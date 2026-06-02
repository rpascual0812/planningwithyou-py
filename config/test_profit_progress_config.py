from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import Tag
from companies.models import Company
from config.models import Config
from config.views import ACTIVE_PROJECTS_SCOPE, PROFIT_PROGRESS_SCOPE
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account
from users.roles import ensure_owner_role

User = get_user_model()


class ProfitProgressTagConfigTests(TestCase):
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
        owner = ensure_owner_role(self.account)
        self.user = User.objects.create_user(
            username='cfg@test.com',
            email='cfg@test.com',
            password='test-pass',
            account=self.account,
            company=self.company,
            role=owner,
            is_verified=True,
        )
        self.tag = Tag.objects.create(
            account=self.account,
            company=self.company,
            tag='completed',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_put_and_get_profit_progress_tag_config(self):
        put_res = self.client.put(
            '/config/profit-progress-tag/',
            {'company_id': self.company.pk, 'value': str(self.tag.pk)},
            format='json',
        )
        self.assertEqual(put_res.status_code, 200)
        self.assertEqual(put_res.data['scope'], PROFIT_PROGRESS_SCOPE)
        self.assertEqual(put_res.data['name'], 'tag')
        self.assertEqual(put_res.data['company_id'], self.company.pk)
        self.assertEqual(put_res.data['value'], str(self.tag.pk))

        row = Config.objects.get(
            account=self.account,
            company=self.company,
            scope=PROFIT_PROGRESS_SCOPE,
            name='tag',
        )
        self.assertEqual(row.value, str(self.tag.pk))

        get_res = self.client.get(
            f'/config/profit-progress-tag/?company_id={self.company.pk}',
        )
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.data['value'], str(self.tag.pk))

    def test_put_and_get_active_projects_tag_config(self):
        put_res = self.client.put(
            '/config/active-projects-tag/',
            {'company_id': self.company.pk, 'value': str(self.tag.pk)},
            format='json',
        )
        self.assertEqual(put_res.status_code, 200)
        self.assertEqual(put_res.data['scope'], ACTIVE_PROJECTS_SCOPE)

        row = Config.objects.get(
            account=self.account,
            company=self.company,
            scope=ACTIVE_PROJECTS_SCOPE,
            name='tag',
        )
        self.assertEqual(row.value, str(self.tag.pk))

    def test_put_rejects_foreign_tag(self):
        other_account = Account.objects.create(
            name='Other',
            country=self.account.country,
        )
        foreign = Tag.objects.create(account=other_account, tag='other')

        res = self.client.put(
            '/config/profit-progress-tag/',
            {'company_id': self.company.pk, 'value': str(foreign.pk)},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
