from django.contrib.auth import get_user_model
from django.test import TestCase

from companies.models import Company
from countries.models import Country
from emails.mail import create_and_queue_email
from emails.models import EmailLog, EmailTemplate
from suppliers.models import SupplierType
from users.models import Account

User = get_user_model()


class TemplateCcBccQueueTests(TestCase):
    def setUp(self):
        country = Country.objects.create(
            name='Testland',
            iso_code='TLD',
            iso2_code='TL',
            currency='Peso',
            currency_symbol='P',
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
        self.template = EmailTemplate.objects.create(
            account=self.account,
            company=self.company,
            name='test_tpl',
            title='Test',
            template_type=EmailTemplate.TemplateType.CALENDAR,
            cc=['cc@example.com'],
            bcc=['bcc@example.com'],
        )

    def test_create_and_queue_email_applies_template_cc_bcc(self):
        log = create_and_queue_email(
            to=['guest@example.com'],
            cc=['creator@example.com'],
            subject='Hello',
            body='<p>Hi</p>',
            email_template=self.template,
            account=self.account,
            company=self.company,
        )
        self.assertEqual(log.cc, ['creator@example.com', 'cc@example.com'])
        self.assertEqual(log.bcc, ['bcc@example.com'])
        persisted = EmailLog.objects.get(pk=log.pk)
        self.assertEqual(persisted.cc, log.cc)
        self.assertEqual(persisted.bcc, log.bcc)
