from rest_framework.test import APITestCase

from bookings.models import BookingItem, BookingStatus
from users.test_support import assign_owner_role


class BookingItemPaginationTests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from companies.models import Company
        from users.models import Account

        User = get_user_model()
        self.account = Account.objects.create(name='Pag Account', is_active=True)
        self.company = Company.objects.create(
            account=self.account,
            name='Pag Co',
            is_active=True,
            is_main=True,
        )
        self.user = User.objects.create_user(
            username='paguser',
            email='pag@example.com',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        assign_owner_role(self.user)
        self.status = BookingStatus.objects.create(
            account=self.account,
            title='Open',
            sort_order=0,
        )

    def test_list_all_returns_unpaginated_array(self):
        self.client.force_authenticate(user=self.user)
        BookingItem.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0001',
            title='One',
            sort_order=0,
        )
        response = self.client.get('/booking-items/', {'all': 'true'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload, list)
        self.assertEqual(len(payload), 1)

    def test_list_paginates_ten_per_page(self):
        self.client.force_authenticate(user=self.user)
        for i in range(11):
            BookingItem.objects.create(
                account=self.account,
                company=self.company,
                status=self.status,
                unique_id=f'26-{i:04d}',
                title=f'Booking {i}',
                sort_order=i,
            )

        page_one = self.client.get('/booking-items/')
        self.assertEqual(page_one.status_code, 200)
        body_one = page_one.json()
        self.assertEqual(body_one['count'], 11)
        self.assertEqual(len(body_one['results']), 10)
        self.assertIsNotNone(body_one['next'])

        page_two = self.client.get('/booking-items/', {'page': 2})
        self.assertEqual(page_two.status_code, 200)
        body_two = page_two.json()
        self.assertEqual(len(body_two['results']), 1)
        self.assertIsNone(body_two['next'])
