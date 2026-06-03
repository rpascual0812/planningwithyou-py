from django.test import SimpleTestCase

from emails.models import EmailTemplate
from emails.recipients import merge_recipient_lists, resolve_template_cc_bcc


class MergeRecipientListsTests(SimpleTestCase):
    def test_dedupes_case_insensitive(self):
        result = merge_recipient_lists(
            ['Ops@Example.com', 'ops@example.com'],
            ['audit@example.com'],
        )
        self.assertEqual(result, ['Ops@Example.com', 'audit@example.com'])

    def test_excludes_to_recipients(self):
        result = merge_recipient_lists(
            ['guest@example.com', 'ops@example.com'],
            exclude=['Guest@Example.com'],
        )
        self.assertEqual(result, ['ops@example.com'])


class ResolveTemplateCcBccTests(SimpleTestCase):
    def test_merges_explicit_and_template_lists(self):
        template = EmailTemplate(cc=['tpl-cc@example.com'], bcc=['tpl-bcc@example.com'])
        cc, bcc = resolve_template_cc_bcc(
            template,
            cc=['extra@example.com'],
            bcc=[],
            exclude_to=['guest@example.com'],
        )
        self.assertEqual(cc, ['extra@example.com', 'tpl-cc@example.com'])
        self.assertEqual(bcc, ['tpl-bcc@example.com'])

    def test_without_template_returns_explicit_only(self):
        cc, bcc = resolve_template_cc_bcc(
            None,
            cc=['only@example.com'],
            bcc=['hidden@example.com'],
        )
        self.assertEqual(cc, ['only@example.com'])
        self.assertEqual(bcc, ['hidden@example.com'])
