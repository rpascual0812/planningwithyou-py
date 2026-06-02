from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from bookings.models import BookingStatus, Tag
from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account
from users.roles import ensure_owner_role

User = get_user_model()


class TagApiTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
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
            username='taguser',
            email='tag@example.com',
            password='secret',
            account=self.account,
            company=self.company,
            role=owner,
            is_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_tag_and_deduplicate(self):
        res = self.client.post('/tags/', {'tag': 'VIP'}, format='json')
        self.assertEqual(res.status_code, 201)
        tag_id = res.data['id']
        res2 = self.client.post('/tags/', {'tag': 'vip'}, format='json')
        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.data['id'], tag_id)
        self.assertEqual(Tag.objects.filter(account=self.account).count(), 1)

    def test_search_tags(self):
        Tag.objects.create(account=self.account, tag='Urgent', created_by=self.user)
        Tag.objects.create(account=self.account, tag='Follow-up', created_by=self.user)
        res = self.client.get('/tags/?search=urg')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['tag'], 'Urgent')

    def test_booking_status_with_tags(self):
        tag = Tag.objects.create(account=self.account, tag='Hot', created_by=self.user)
        res = self.client.post(
            '/booking-statuses/',
            {
                'title': 'Qualified',
                'description': '',
                'color': '#1f3a5f',
                'tag_ids': [tag.id],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        status = BookingStatus.objects.get(pk=res.data['id'])
        self.assertEqual(list(status.tags.values_list('id', flat=True)), [tag.id])
        self.assertEqual(len(res.data['tags']), 1)
        self.assertEqual(res.data['tags'][0]['tag'], 'Hot')
