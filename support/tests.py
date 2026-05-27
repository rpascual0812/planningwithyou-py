from django.test import TestCase
from rest_framework.test import APIClient

from countries.models import Country
from support.models import SupportTicket, SupportTicketRead
from users.models import Account, User
from users.test_support import assign_owner_role, grant_platform_admin


class SupportTicketApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        cls.account = Account.objects.create(name='Test Co', country=country)
        cls.user = User.objects.create_user(
            username='user@example.com',
            email='user@example.com',
            password='test-pass',
            account=cls.account,
        )
        assign_owner_role(cls.user)
        cls.other = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='test-pass',
            account=cls.account,
        )
        assign_owner_role(cls.other)
        cls.admin = User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='test-pass',
            account=cls.account,
        )
        grant_platform_admin(cls.admin)

    def setUp(self):
        self.client = APIClient()

    def test_user_creates_ticket_with_initial_message(self):
        self.client.force_authenticate(user=self.user)
        create = self.client.post(
            '/support-tickets/',
            {'title': 'Help', 'message': '<p>Need assistance</p>'},
            format='json',
        )
        self.assertEqual(create.status_code, 201)
        data = create.json()
        self.assertEqual(data['title'], 'Help')
        self.assertEqual(len(data['messages']), 1)
        self.assertEqual(data['messages'][0]['body'], '<p>Need assistance</p>')
        self.assertFalse(data['messages'][0]['is_staff'])

    def test_user_and_staff_exchange_messages(self):
        self.client.force_authenticate(user=self.user)
        create = self.client.post(
            '/support-tickets/',
            {'title': 'Chat', 'message': '<p>Hello support</p>'},
            format='json',
        )
        ticket_id = create.json()['id']

        self.client.force_authenticate(user=self.admin)
        staff_reply = self.client.post(
            f'/admin/support-tickets/{ticket_id}/messages/',
            {'body': '<p>We are looking into it</p>'},
            format='json',
        )
        self.assertEqual(staff_reply.status_code, 201)
        self.assertTrue(staff_reply.json()['is_staff'])

        self.assertFalse(
            SupportTicketRead.objects.filter(
                ticket_id=ticket_id,
                user_id=self.user.pk,
            ).exists(),
        )

        self.client.force_authenticate(user=self.user)
        user_reply = self.client.post(
            f'/support-tickets/{ticket_id}/messages/',
            {'body': '<p>Thanks</p>'},
            format='json',
        )
        self.assertEqual(user_reply.status_code, 201)

        detail = self.client.get(f'/support-tickets/{ticket_id}/')
        self.assertEqual(len(detail.json()['messages']), 3)

    def test_only_creator_can_delete(self):
        self.client.force_authenticate(user=self.user)
        create = self.client.post(
            '/support-tickets/',
            {'title': 'Delete me', 'message': '<p>Body</p>'},
            format='json',
        )
        ticket_id = create.json()['id']

        self.client.force_authenticate(user=self.other)
        denied = self.client.delete(f'/support-tickets/{ticket_id}/')
        self.assertEqual(denied.status_code, 404)

        self.client.force_authenticate(user=self.user)
        ok = self.client.delete(f'/support-tickets/{ticket_id}/')
        self.assertEqual(ok.status_code, 204)
        self.assertIsNotNone(
            SupportTicket.all_objects.get(pk=ticket_id).deleted_at,
        )

    def test_admin_status_update_clears_creator_read(self):
        self.client.force_authenticate(user=self.user)
        create = self.client.post(
            '/support-tickets/',
            {'title': 'Status', 'message': '<p>Please help</p>'},
            format='json',
        )
        ticket_id = create.json()['id']
        self.client.get(f'/support-tickets/{ticket_id}/')

        self.client.force_authenticate(user=self.admin)
        patch = self.client.patch(
            f'/admin/support-tickets/{ticket_id}/',
            {'status': 'in_progress'},
            format='json',
        )
        self.assertEqual(patch.status_code, 200)
        self.assertFalse(
            SupportTicketRead.objects.filter(
                ticket_id=ticket_id,
                user_id=self.user.pk,
            ).exists(),
        )

        self.client.force_authenticate(user=self.user)
        listing = self.client.get('/support-tickets/')
        self.assertFalse(listing.json()[0]['is_read'])
