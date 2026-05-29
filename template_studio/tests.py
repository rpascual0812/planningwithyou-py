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

    def test_create_rejects_duplicate_title(self):
        res1 = self.client.post(
            '/template-studio/templates/',
            {'title': 'Unique Wedding', 'document': self.doc},
            format='json',
        )
        self.assertEqual(res1.status_code, 201, res1.data)
        res2 = self.client.post(
            '/template-studio/templates/',
            {'title': 'Unique Wedding', 'document': self.doc},
            format='json',
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn('title', res2.data)

    def test_update_rejects_duplicate_title(self):
        first = self.client.post(
            '/template-studio/templates/',
            {'title': 'First Invite', 'document': self.doc},
            format='json',
        )
        second = self.client.post(
            '/template-studio/templates/',
            {'title': 'Second Invite', 'document': self.doc},
            format='json',
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        res = self.client.patch(
            f'/template-studio/templates/{second.data["id"]}/',
            {'title': 'First Invite'},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('title', res.data)

    def test_create_assigns_unique_slug_globally(self):
        other_company = Company.objects.create(
            account=self.account,
            name='Other Co',
            supplier_type=self.supplier_type,
            is_main=False,
        )
        other_user = User.objects.create_user(
            username='other@test.example',
            email='other@test.example',
            password='secret12',
            account=self.account,
            company=other_company,
            is_verified=True,
        )
        InvitationTemplate.objects.create(
            account=self.account,
            company=self.company,
            title='Shared Slug Test',
            slug='shared-slug',
            document=self.doc,
            created_by=self.user,
        )
        self.client.force_authenticate(user=other_user)
        res = self.client.post(
            '/template-studio/templates/',
            {'title': 'Shared Slug Test', 'document': self.doc},
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertNotEqual(res.data['slug'], 'shared-slug')

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

    def test_public_rsvp_submit(self):
        doc = {
            **self.doc,
            'pages': [
                {
                    'id': 'p1',
                    'name': 'RSVP',
                    'slug': 'rsvp',
                    'sectionType': 'rsvp',
                    'width': 1280,
                    'height': 720,
                    'background': {'type': 'solid', 'color': '#fff'},
                    'elements': [
                        {
                            'id': 'rsvp_el_1',
                            'type': 'rsvp',
                            'name': 'RSVP',
                            'heading': 'Please RSVP',
                            'submitLabel': 'Submit',
                            'fields': [
                                {
                                    'id': 'first_name',
                                    'label': 'First Name',
                                    'type': 'text',
                                    'required': True,
                                },
                                {
                                    'id': 'email_address',
                                    'label': 'Email Address',
                                    'type': 'email',
                                    'required': True,
                                },
                            ],
                            'transform': {
                                'x': 0,
                                'y': 0,
                                'width': 400,
                                'height': 300,
                                'rotation': 0,
                                'scaleX': 1,
                                'scaleY': 1,
                                'opacity': 1,
                                'zIndex': 1,
                            },
                        }
                    ],
                }
            ],
        }
        tpl = InvitationTemplate.objects.create(
            account=self.account,
            company=self.company,
            title='RSVP Wedding',
            slug='rsvp-wedding-test',
            document=doc,
            is_published=True,
            created_by=self.user,
        )
        res = self.client.post(
            f'/public/invitations/{tpl.slug}/rsvp/',
            {
                'element_id': 'rsvp_el_1',
                'fields': {
                    'first_name': 'Jane',
                    'email_address': 'jane@example.com',
                },
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        from template_studio.models import InvitationRsvp

        rsvp = InvitationRsvp.objects.get(invitation_template=tpl)
        self.assertEqual(rsvp.element_id, 'rsvp_el_1')
        self.assertEqual(rsvp.fields_data['first_name'], 'Jane')
        self.assertEqual(rsvp.fields_data['email_address'], 'jane@example.com')

    def test_public_rsvp_required_field_validation(self):
        doc = {
            **self.doc,
            'pages': [
                {
                    'id': 'p1',
                    'name': 'RSVP',
                    'slug': 'rsvp',
                    'sectionType': 'rsvp',
                    'width': 1280,
                    'height': 720,
                    'background': {'type': 'solid', 'color': '#fff'},
                    'elements': [
                        {
                            'id': 'rsvp_el_1',
                            'type': 'rsvp',
                            'name': 'RSVP',
                            'heading': 'Please RSVP',
                            'submitLabel': 'Submit',
                            'fields': [
                                {
                                    'id': 'first_name',
                                    'label': 'First Name',
                                    'type': 'text',
                                    'required': True,
                                },
                            ],
                            'transform': {
                                'x': 0,
                                'y': 0,
                                'width': 400,
                                'height': 300,
                                'rotation': 0,
                                'scaleX': 1,
                                'scaleY': 1,
                                'opacity': 1,
                                'zIndex': 1,
                            },
                        }
                    ],
                }
            ],
        }
        tpl = InvitationTemplate.objects.create(
            account=self.account,
            company=self.company,
            title='RSVP Validation',
            slug='rsvp-validation-test',
            document=doc,
            is_published=True,
            created_by=self.user,
        )
        res = self.client.post(
            f'/public/invitations/{tpl.slug}/rsvp/',
            {'element_id': 'rsvp_el_1', 'fields': {}},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('first_name', res.data['fields'])

    def _rsvp_document(self):
        return {
            **self.doc,
            'pages': [
                {
                    'id': 'p1',
                    'name': 'RSVP',
                    'slug': 'rsvp',
                    'sectionType': 'rsvp',
                    'width': 1280,
                    'height': 720,
                    'background': {'type': 'solid', 'color': '#fff'},
                    'elements': [
                        {
                            'id': 'rsvp_el_1',
                            'type': 'rsvp',
                            'name': 'RSVP',
                            'heading': 'Please RSVP',
                            'submitLabel': 'Submit',
                            'fields': [
                                {
                                    'id': 'first_name',
                                    'label': 'First Name',
                                    'type': 'text',
                                    'required': True,
                                },
                                {
                                    'id': 'email_address',
                                    'label': 'Email Address',
                                    'type': 'email',
                                    'required': True,
                                },
                            ],
                            'transform': {
                                'x': 0,
                                'y': 0,
                                'width': 400,
                                'height': 300,
                                'rotation': 0,
                                'scaleX': 1,
                                'scaleY': 1,
                                'opacity': 1,
                                'zIndex': 1,
                            },
                        }
                    ],
                }
            ],
        }

    def test_public_rsvp_list(self):
        from template_studio.models import InvitationRsvp

        tpl = InvitationTemplate.objects.create(
            account=self.account,
            company=self.company,
            title='RSVP List Test',
            slug='rsvp-list-test',
            document=self._rsvp_document(),
            is_published=True,
            created_by=self.user,
        )
        InvitationRsvp.objects.create(
            invitation_template=tpl,
            element_id='rsvp_el_1',
            fields_data={'first_name': 'Jane', 'email_address': 'jane@example.com'},
        )
        self.client.logout()
        res = self.client.get(f'/public/invitations/{tpl.slug}/rsvp/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['title'], 'RSVP List Test')
        self.assertEqual(len(res.data['results']), 1)
        self.assertEqual(res.data['results'][0]['fields_data']['first_name'], 'Jane')
        self.assertTrue(any(c['id'] == 'first_name' for c in res.data['field_columns']))

    def test_public_rsvp_export_xlsx(self):
        from template_studio.models import InvitationRsvp

        tpl = InvitationTemplate.objects.create(
            account=self.account,
            company=self.company,
            title='RSVP Export Test',
            slug='rsvp-export-test',
            document=self._rsvp_document(),
            is_published=True,
            created_by=self.user,
        )
        InvitationRsvp.objects.create(
            invitation_template=tpl,
            element_id='rsvp_el_1',
            fields_data={'first_name': 'Bob', 'email_address': 'bob@example.com'},
        )
        self.client.logout()
        res = self.client.get(f'/public/invitations/{tpl.slug}/rsvp/export/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(
            'spreadsheetml.sheet',
            res['Content-Type'],
        )
        self.assertIn('attachment', res['Content-Disposition'])
        self.assertTrue(len(res.content) > 100)
