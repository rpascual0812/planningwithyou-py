from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


def _jpeg_upload(name: str = 'photo.jpg', size=(400, 300)) -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new('RGB', size, color=(200, 50, 50)).save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='image/jpeg')


class UserPhotoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.create(
            name='Philippines',
            iso_code='PHL',
            iso2_code='PH',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        cls.supplier_type = SupplierType.objects.create(name='Planner')

    def setUp(self):
        self.client = APIClient()
        self.account = Account.objects.create(
            name='Tenant',
            country=self.country,
            is_active=True,
        )
        self.company = Company.objects.create(
            account=self.account,
            name='Main Co',
            supplier_type=self.supplier_type,
            is_main=True,
            is_active=True,
        )
        self.user = User.objects.create_user(
            username='photo@test.example',
            email='photo@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        self.other = User.objects.create_user(
            username='other@test.example',
            email='other@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_me_includes_photo_url_after_upload(self):
        self.assertEqual(self.client.get('/api/users/me/').data['photo_url'], '')

        res = self.client.patch(
            f'/api/users/{self.user.pk}/',
            {'photo': _jpeg_upload()},
            format='multipart',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['photo_url'])

        me = self.client.get('/api/users/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data['photo_url'], res.data['photo_url'])

        file_res = self.client.get(f'/api/files/u/{self.user.pk}/photo/')
        self.assertEqual(file_res.status_code, 200)
        self.assertIn('image/', file_res['Content-Type'])

    def test_cannot_upload_photo_for_another_user(self):
        res = self.client.patch(
            f'/api/users/{self.other.pk}/',
            {'photo': _jpeg_upload()},
            format='multipart',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('photo_upload', res.data)
