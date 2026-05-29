from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from countries.models import Country
from suppliers.models import SupplierType
from template_studio.models import InvitationTemplate
from users.models import Account, User


class InvitationTemplateApiTests(TestCase):
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
        self.account = Account.objects.create(name='Tenant', country=self.country)
        self.company = Company.objects.create(
            account=self.account,
            name='Main Co',
            supplier_type=self.supplier_type,
            is_main=True,
        )
        self.user = User.objects.create_user(
            username='editor@test.example',
            email='editor@test.example',
            password='secret12',
            account=self.account,
            company=self.company,
            is_verified=True,
        )
        from users.roles import ensure_owner_role
        ensure_owner_role(self.account)
        self.client.force_authenticate(user=self.user)
        self.doc = {
            'schemaVersion': 1,
            'meta': {
                'id': 'tpl_test',
                'title': 'Our Wedding',
                'name': 'Our Wedding',
                'description': 'Test',
                'category': 'wedding',
                'tags': [],
                'version': 1,
                'createdAt': '2026-01-01T00:00:00Z',
                'updatedAt': '2026-01-01T00:00:00Z',
            },
            'pages': [],
            'globalFonts': [],
            'settings': {
                'snapGrid': 8,
                'showGuides': True,
                'defaultPageSize': {'width': 390, 'height': 844},
            },
        }

    def test_create_template_with_title(self):
        res = self.client.post(
            '/template-studio/templates/',
            {'title': 'Summer Wedding', 'document': self.doc},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['title'], 'Summer Wedding')
        self.assertTrue(res.data['slug'])

    def test_create_without_slug_in_payload(self):
        """Slug is server-generated; clients must not be required to send it."""
        res = self.client.post(
            '/template-studio/templates/',
            {'title': 'No Slug Sent', 'document': self.doc},
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data['slug'])

    def test_create_requires_title(self):
        res = self.client.post(
            '/template-studio/templates/',
            {'document': self.doc},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('title', res.data)

    def test_publish_and_public_read(self):
        create = self.client.post(
            '/template-studio/templates/',
            {'title': 'Public Invite', 'document': self.doc},
            format='json',
        )
        tpl_id = create.data['id']
        pub = self.client.post(f'/template-studio/templates/{tpl_id}/publish/')
        self.assertEqual(pub.status_code, 200)
        slug = pub.data['slug']
        self.client.logout()
        public = self.client.get(f'/public/invitations/{slug}/')
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.data['title'], 'Public Invite')

    def test_republish_keeps_slug_when_title_changes(self):
        create = self.client.post(
            '/template-studio/templates/',
            {'title': 'Original Title', 'document': self.doc},
            format='json',
        )
        tpl_id = create.data['id']
        original_slug = create.data['slug']
        first_pub = self.client.post(f'/template-studio/templates/{tpl_id}/publish/')
        self.assertEqual(first_pub.data['slug'], original_slug)

        updated_doc = {**self.doc, 'meta': {**self.doc['meta'], 'title': 'Renamed Wedding'}}
        patch = self.client.patch(
            f'/template-studio/templates/{tpl_id}/',
            {'title': 'Renamed Wedding', 'document': updated_doc},
            format='json',
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.data['slug'], original_slug)

        second_pub = self.client.post(f'/template-studio/templates/{tpl_id}/publish/')
        self.assertEqual(second_pub.status_code, 200)
        self.assertEqual(second_pub.data['slug'], original_slug)
        self.assertTrue(second_pub.data['is_published'])

    def test_marketplace_includes_modern_elegance(self):
        InvitationTemplate.objects.filter(
            slug='tan-beige-modern-elegance',
            is_marketplace=True,
        ).delete()
        from template_studio.canva_modern_elegance_document import MARKETPLACE_ENTRY
        InvitationTemplate.objects.create(
            title=MARKETPLACE_ENTRY['title'],
            slug=MARKETPLACE_ENTRY['slug'],
            category=MARKETPLACE_ENTRY['category'],
            description=MARKETPLACE_ENTRY['description'],
            document=MARKETPLACE_ENTRY['document'],
            marketplace_preview_url=MARKETPLACE_ENTRY['marketplace_preview_url'],
            is_marketplace=True,
        )
        res = self.client.get('/template-studio/marketplace/')
        self.assertEqual(res.status_code, 200)
        row = next(r for r in res.data if r['slug'] == 'tan-beige-modern-elegance')
        self.assertEqual(row['title'], 'Tan Beige Modern Elegance')
        self.assertEqual(len(row['document']['pages']), 6)

    def test_upload_template_asset(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        image = SimpleUploadedFile(
            'photo.png',
            BytesIO(b'\x89PNG\r\n\x1a\n').getvalue(),
            content_type='image/png',
        )
        res = self.client.post(
            '/template-studio/assets/upload/',
            {'file': image},
            format='multipart',
        )
        self.assertEqual(res.status_code, 201, res.data)
        asset_uuid = res.data['uuid']
        self.assertTrue(res.data['url'])

        public = self.client.get(f'/public/template-assets/{asset_uuid}/')
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public['Content-Type'], 'image/png')

    def test_marketplace_list(self):
        InvitationTemplate.objects.create(
            title='Catalog Item',
            slug='catalog-item',
            category='wedding',
            document=self.doc,
            is_marketplace=True,
        )
        res = self.client.get('/template-studio/marketplace/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any(r['title'] == 'Catalog Item' for r in res.data))
