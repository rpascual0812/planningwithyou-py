from rest_framework.test import APITestCase

from bookings.models import BookingItem, BookingStatus
from companies.models import Company
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
            company=self.company,
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

    def test_board_view_returns_slim_payload(self):
        self.client.force_authenticate(user=self.user)
        BookingItem.objects.create(
            account=self.account,
            company=self.company,
            status=self.status,
            unique_id='26-0100',
            title='Board One',
            sort_order=0,
        )
        response = self.client.get(
            '/booking-items/',
            {'view': 'board', 'board_column': str(self.status.id)},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['count'], 1)
        row = body['results'][0]
        self.assertEqual(row['title'], 'Board One')
        self.assertIn('paid_amount', row)
        self.assertNotIn('field_values', row)
        self.assertNotIn('groups', row)

    def test_board_column_paginates_per_status(self):
        self.client.force_authenticate(user=self.user)
        other_status = BookingStatus.objects.create(
            account=self.account,
            company=self.company,
            title='Done',
            sort_order=1,
        )
        for i in range(11):
            BookingItem.objects.create(
                account=self.account,
                company=self.company,
                status=self.status,
                unique_id=f'26-{i:04d}',
                title=f'Open {i}',
                sort_order=i,
            )
        BookingItem.objects.create(
            account=self.account,
            company=self.company,
            status=other_status,
            unique_id='26-9999',
            title='Done booking',
            sort_order=0,
        )

        page_one = self.client.get(
            '/booking-items/',
            {'view': 'board', 'board_column': str(self.status.id), 'page': 1},
        )
        self.assertEqual(page_one.status_code, 200)
        body_one = page_one.json()
        self.assertEqual(body_one['count'], 11)
        self.assertEqual(len(body_one['results']), 10)
        self.assertIsNotNone(body_one['next'])

        page_two = self.client.get(
            '/booking-items/',
            {'view': 'board', 'board_column': str(self.status.id), 'page': 2},
        )
        self.assertEqual(len(page_two.json()['results']), 1)

        done_page = self.client.get(
            '/booking-items/',
            {'view': 'board', 'board_column': str(other_status.id)},
        )
        self.assertEqual(done_page.json()['count'], 1)

    def test_board_column_matches_foreign_status_by_title(self):
        self.client.force_authenticate(user=self.user)
        tenant = Company.objects.create(
            account=self.account,
            name='Tenant Co',
            is_active=True,
        )
        tenant_status = BookingStatus.objects.create(
            account=self.account,
            company=tenant,
            title='Open',
            sort_order=99,
        )
        BookingItem.objects.create(
            account=self.account,
            company=tenant,
            status=tenant_status,
            unique_id='26-0200',
            title='Tenant booking',
            sort_order=0,
        )

        response = self.client.get(
            '/booking-items/',
            {'view': 'board', 'board_column': str(self.status.id)},
        )
        self.assertEqual(response.status_code, 200)
        titles = [row['title'] for row in response.json()['results']]
        self.assertIn('Tenant booking', titles)

    def test_board_foreign_slot_excludes_title_matched(self):
        self.client.force_authenticate(user=self.user)
        tenant = Company.objects.create(
            account=self.account,
            name='Tenant Co',
            is_active=True,
        )
        tenant_status = BookingStatus.objects.create(
            account=self.account,
            company=tenant,
            title='Mystery',
            sort_order=99,
        )
        BookingItem.objects.create(
            account=self.account,
            company=tenant,
            status=tenant_status,
            unique_id='26-0300',
            title='Unmatched foreign',
            sort_order=0,
        )

        response = self.client.get(
            '/booking-items/',
            {'view': 'board', 'board_slot': 'foreign'},
        )
        self.assertEqual(response.status_code, 200)
        titles = [row['title'] for row in response.json()['results']]
        self.assertIn('Unmatched foreign', titles)

        matched = self.client.get(
            '/booking-items/',
            {
                'view': 'board',
                'board_column': str(self.status.id),
            },
        )
        self.assertNotIn('Unmatched foreign', [r['title'] for r in matched.json()['results']])
