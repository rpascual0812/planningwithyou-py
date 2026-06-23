from django.test import SimpleTestCase

from subscriptions.xendit_client import format_xendit_error_message


class XenditClientErrorFormattingTests(SimpleTestCase):
    def test_includes_structured_validation_errors(self):
        message = format_xendit_error_message(
            {
                'message': 'Failed to validate the request, 2 errors occurred.',
                'errors': [
                    {
                        'path': 'body.description',
                        'message': 'JSON string does not match the regular expression',
                    },
                    {
                        'path': 'body.routes.0.destination_account_id',
                        'message': "Property 'destination_account_id' is missing",
                    },
                ],
            },
            status_code=400,
        )
        self.assertIn('body.description:', message)
        self.assertIn('destination_account_id', message)
        self.assertNotIn('XENDIT_RETURN_URL_BASE', message)
