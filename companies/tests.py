from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company, CompanyKybVerification
from countries.models import Country
from documents.models import DocumentFolder
from emails.models import EmailTemplate
from suppliers.models import SupplierType, Tier
from users.models import Account, User
from users.test_support import assign_owner_role


class CompanyMainFlagTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Dollar',
            currency_symbol='$',
            currency_code='USD',
        )
        self.supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(
            name='Test Account',
            country=country,
        )
        self.first = Company.objects.create(
            account=self.account,
            name='First Co',
            supplier_type=self.supplier_type,
            is_main=True,
        )
        self.second = Company.objects.create(
            account=self.account,
            name='Second Co',
            supplier_type=self.supplier_type,
            is_main=False,
        )

    def test_update_second_to_main_clears_first(self):
        self.second.is_main = True
        self.second.save(update_fields=['is_main'])

        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertFalse(self.first.is_main)
        self.assertTrue(self.second.is_main)
        self.assertEqual(
            Company.objects.filter(account=self.account, is_main=True).count(),
            1,
        )

    def test_create_main_clears_existing_main(self):
        third = Company(
            account=self.account,
            name='Third Co',
            supplier_type=self.supplier_type,
            is_main=True,
        )
        third.save()

        self.first.refresh_from_db()
        third.refresh_from_db()
        self.assertFalse(self.first.is_main)
        self.assertTrue(third.is_main)


class CompanyKybVerifiedTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='KYBland',
            iso_code='KYB',
            iso2_code='KB',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        supplier_type = SupplierType.objects.create(name='Events')
        account = Account.objects.create(name='KYB Account', country=country)
        self.company = Company.objects.create(
            account=account,
            name='KYB Co',
            supplier_type=supplier_type,
        )

    def test_kyb_approved_sets_company_kyb_verified(self):
        kyb = CompanyKybVerification.objects.create(company=self.company)
        self.assertFalse(self.company.kyb_verified)

        kyb.paymongo_status = CompanyKybVerification.PaymongoStatus.APPROVED
        kyb.save()

        self.company.refresh_from_db()
        self.assertTrue(self.company.kyb_verified)

    def test_kyb_rejected_clears_company_kyb_verified(self):
        kyb = CompanyKybVerification.objects.create(
            company=self.company,
            paymongo_status=CompanyKybVerification.PaymongoStatus.APPROVED,
        )
        self.company.refresh_from_db()
        self.assertTrue(self.company.kyb_verified)

        kyb.paymongo_status = CompanyKybVerification.PaymongoStatus.REJECTED
        kyb.save()

        self.company.refresh_from_db()
        self.assertFalse(self.company.kyb_verified)


class CompanyKybAdminApiTests(TestCase):
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
            name='Verify Me Co',
            supplier_type=supplier_type,
            is_main=True,
        )
        self.kyb = CompanyKybVerification.objects.create(
            company=self.company,
            paymongo_status=CompanyKybVerification.PaymongoStatus.PENDING_PAYMONGO,
            business_type=CompanyKybVerification.BusinessType.SOLE_PROPRIETOR,
            merchant_business_name='Verify Me Co',
            merchant_email='owner@verifyme.test',
            merchant_mobile_number='+639171234567',
        )
        from users.models import User

        from users.test_support import grant_platform_admin

        self.admin = User.objects.create_user(
            username='admin@test.com',
            email='admin@test.com',
            password='test-pass',
            account=self.account,
            company=self.company,
        )
        grant_platform_admin(self.admin)
        self.user = User.objects.create_user(
            username='user@test.com',
            email='user@test.com',
            password='test-pass',
            account=self.account,
            company=self.company,
        )

    def test_admin_lists_pending_paymongo_kyb(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.get(
            '/admin/kyb-verifications/',
            {'paymongo_status': CompanyKybVerification.PaymongoStatus.PENDING_PAYMONGO},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['company_name'], 'Verify Me Co')

    def test_non_admin_cannot_list_kyb(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get('/admin/kyb-verifications/')
        self.assertEqual(res.status_code, 403)

    def test_admin_approves_kyb(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.patch(
            f'/admin/kyb-verifications/{self.kyb.pk}/',
            {'paymongo_status': CompanyKybVerification.PaymongoStatus.APPROVED},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.kyb.refresh_from_db()
        self.assertEqual(self.kyb.paymongo_status, CompanyKybVerification.PaymongoStatus.APPROVED)
        self.company.refresh_from_db()
        self.assertTrue(self.company.kyb_verified)


class CompanyCreateDefaultsApiTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Peso',
            currency_symbol='₱',
            currency_code='PHP',
        )
        self.supplier_type = SupplierType.objects.create(name='General')
        self.account = Account.objects.create(name='Tenant', country=country)
        self.user = User.objects.create_user(
            username='owner@test.com',
            email='owner@test.com',
            password='test-pass',
            account=self.account,
        )
        assign_owner_role(self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_company_seeds_registration_defaults(self):
        res = self.client.post(
            '/companies/',
            {
                'name': 'Branch Co',
                'supplier_type': self.supplier_type.id,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        company_id = res.data['id']

        tiers = set(
            Tier.objects.filter(account=self.account, company_id=company_id).values_list(
                'name',
                flat=True,
            ),
        )
        self.assertEqual(tiers, {'Bronze', 'Silver', 'Gold'})

        templates = set(
            EmailTemplate.objects.filter(
                account=self.account,
                company_id=company_id,
                is_default=True,
            ).values_list('name', flat=True),
        )
        self.assertEqual(
            templates,
            {
                'welcome',
                'verify_email',
                'password_reset',
                'new_quotation',
                'updated_quotation',
                'quotation_status_contact',
                'quotation_status_company',
                'payment_link',
                'payment_received',
                'calendar_event_creation',
                'calendar_event_updated',
            },
        )

        self.assertTrue(
            DocumentFolder.objects.filter(
                account=self.account,
                company_id=company_id,
                name='General',
            ).exists(),
        )

        from bookings.models import QuotationStatus, Tag

        status_titles = list(
            QuotationStatus.objects.filter(
                account=self.account,
                company_id=company_id,
            )
            .order_by('sort_order')
            .values_list('title', flat=True),
        )
        self.assertEqual(
            status_titles,
            ['New', 'Confirmed', 'In-progress', 'Completed', 'Cancelled'],
        )

        tag_names = set(
            Tag.objects.filter(
                account=self.account,
                company_id=company_id,
            ).values_list('tag', flat=True),
        )
        self.assertEqual(
            tag_names,
            {'new', 'confirmed', 'cancelled', 'completed', 'done'},
        )

    def test_company_detail_includes_contact_email_from_first_user(self):
        from companies.models import Company

        company = Company.objects.create(
            account=self.account,
            name='No Email Co',
            supplier_type=self.supplier_type,
            is_active=True,
            contact_email='',
        )
        User.objects.create_user(
            username='first@noemail.test',
            email='first@noemail.test',
            password='test-pass',
            account=self.account,
            company=company,
        )
        User.objects.create_user(
            username='second@noemail.test',
            email='second@noemail.test',
            password='test-pass',
            account=self.account,
            company=company,
        )

        res = self.client.get(f'/companies/{company.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['contact_email'], 'first@noemail.test')

        patch_res = self.client.patch(
            f'/companies/{company.id}/',
            {'contact_email': 'custom@example.com'},
            format='json',
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data['contact_email'], 'custom@example.com')
