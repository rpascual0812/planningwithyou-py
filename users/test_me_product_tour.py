from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from users.models import Account
from users.roles import ensure_owner_role

User = get_user_model()


class MeProductTourTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.account = Account.objects.create(name='Tour Account', is_active=True)
        self.company = Company.objects.create(
            account=self.account,
            name='Tour Co',
            is_active=True,
            is_main=True,
        )
        owner = ensure_owner_role(self.account)
        self.user = User.objects.create_user(
            username='touruser',
            email='tour@example.com',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
            role=owner,
        )
        self.client.force_authenticate(user=self.user)

    def test_complete_product_tour_sets_timestamp(self):
        self.assertIsNone(self.user.tour_completed_at)
        res = self.client.patch(
            '/users/me/',
            {'complete_product_tour': True},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIsNotNone(res.data['tour_completed_at'])
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.tour_completed_at)

    def test_restart_product_tour_clears_timestamp(self):
        self.user.tour_completed_at = self.user.updated_at
        self.user.save(update_fields=['tour_completed_at'])
        res = self.client.patch(
            '/users/me/',
            {'restart_product_tour': True},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data['tour_completed_at'])
